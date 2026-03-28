"""
TENAX-LPR - Endpoints de cámara, análisis de media y WebSocket
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, WebSocket, WebSocketDisconnect

from database import consultar_placa, guardar_historial
from schemas import CamaraIniciar
from vision import detectar_y_leer, detectar_placas, leer_placa, loop_camara
from websocket import manager

router = APIRouter()


def _verificar_modelos(request: Request):
    if request.app.state.yolo is None or request.app.state.ocr is None:
        raise HTTPException(
            status_code=503,
            detail="Modelo YOLO no cargado. Coloca modelo_placas.pt y reinicia la API."
        )


@router.post("/camara/iniciar")
async def iniciar_camara(request: Request, datos: CamaraIniciar = CamaraIniciar()):
    _verificar_modelos(request)

    if request.app.state.camara_task and not request.app.state.camara_task.done():
        raise HTTPException(status_code=409, detail="La camara ya esta activa. Usa POST /camara/detener primero.")

    fuente = (
        int(datos.fuente)
        if datos.fuente is not None and datos.fuente.isdigit()
        else (datos.fuente or 0)
    )

    stop_event = asyncio.Event()
    request.app.state.camara_stop = stop_event
    request.app.state.camara_task = asyncio.create_task(
        loop_camara(request.app.state.yolo, request.app.state.ocr, fuente, stop_event)
    )

    return {"mensaje": "Camara iniciada.", "fuente": str(fuente)}


@router.post("/camara/detener")
async def detener_camara(request: Request):
    if request.app.state.camara_stop is None or (
        request.app.state.camara_task and request.app.state.camara_task.done()
    ):
        raise HTTPException(status_code=409, detail="La camara no esta activa.")

    request.app.state.camara_stop.set()
    return {"mensaje": "Camara detenida."}


@router.post("/analizar-imagen")
async def analizar_imagen(request: Request, imagen: UploadFile = File(...)):
    _verificar_modelos(request)

    contenido = await imagen.read()
    arr       = np.frombuffer(contenido, dtype=np.uint8)
    frame     = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(
            status_code=400,
            detail="No se pudo decodificar la imagen. Asegurate de enviar un archivo valido (jpg, png, etc.)."
        )

    detecciones = detectar_y_leer(frame, request.app.state.yolo, request.app.state.ocr)

    resultados = []
    for det in detecciones:
        numero = det["placa"]
        info   = consultar_placa(numero)
        guardar_historial(numero, info["estado"])

        await manager.broadcast({
            "tipo":      "deteccion",
            "timestamp": datetime.now().isoformat(),
            **info,
            "confianza": det["confianza"],
        })

        resultados.append({
            **info,
            "confianza": det["confianza"],
            "bbox":      det["bbox"],
            "timestamp": datetime.now().isoformat(),
        })

    return {
        "total_detectadas": len(resultados),
        "placas":           resultados,
    }


@router.post("/analizar-video")
async def analizar_video(request: Request, video: UploadFile = File(...)):
    _verificar_modelos(request)

    contenido = await video.read()
    sufijo    = Path(video.filename).suffix if video.filename else ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(contenido)
        ruta_tmp = tmp.name

    cap = cv2.VideoCapture(ruta_tmp)
    if not cap.isOpened():
        os.unlink(ruta_tmp)
        raise HTTPException(status_code=400, detail="No se pudo abrir el archivo de video.")

    placas_vistas = {}
    frame_num     = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 1. YOLO revisa cada frame — solo continúa si detecta una placa
        recortes = detectar_placas(frame, request.app.state.yolo)
        if not recortes:
            frame_num += 1
            continue

        # 2. Solo los frames con placa pasan al OCR
        for rec in recortes:
            numero = leer_placa(rec["recorte"], request.app.state.ocr)
            if numero is None or numero in placas_vistas:
                continue

            info = consultar_placa(numero)
            guardar_historial(numero, info["estado"])
            placas_vistas[numero] = {
                **info,
                "confianza": rec["confianza"],
                "frame":     frame_num,
                "timestamp": datetime.now().isoformat(),
            }
            await manager.broadcast({
                "tipo":      "deteccion",
                "timestamp": datetime.now().isoformat(),
                **info,
                "confianza": rec["confianza"],
            })

        frame_num += 1

    cap.release()
    os.unlink(ruta_tmp)

    return {
        "total_frames":     frame_num,
        "total_detectadas": len(placas_vistas),
        "placas":           list(placas_vistas.values()),
    }


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.conectar(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.desconectar(ws)
