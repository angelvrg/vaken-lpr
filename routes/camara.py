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
from vision import detectar_y_leer, detectar_placas_batch, leer_placas_batch, leer_placa, loop_camara, es_misma_placa
from websocket import manager

router = APIRouter()


def _verificar_modelos(request: Request):
    if request.app.state.yolo is None or request.app.state.ocr is None:
        raise HTTPException(
            status_code=503,
            detail="Modelos no cargados. Revisa la consola al iniciar."
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


# ---------------------------------------------------------------------------
# PROCESAMIENTO DE VIDEO (SÍNCRONO, EJECUTADO EN THREAD)
# ---------------------------------------------------------------------------

def _procesar_video_sync(ruta_tmp: str, yolo, ocr) -> dict:
    """Lógica síncrona de procesamiento de video, ejecutada en un thread separado."""
    cap = cv2.VideoCapture(ruta_tmp)
    if not cap.isOpened():
        return {"error": "No se pudo abrir el archivo de video."}

    placas_vistas = {}
    placas_set = set()
    frame_num = 0
    ultimo_tuvo_deteccion = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_num += 1

        # Frame skip adaptativo
        frame_skip = 5 if ultimo_tuvo_deteccion else 20
        if frame_num % frame_skip != 0:
            continue

        # Batch YOLO: acumular frames y procesar en batch
        frames_buffer = [frame]
        for _ in range(3):
            ret_next, frame_next = cap.read()
            if not ret_next:
                break
            frame_num += 1
            frames_buffer.append(frame_next)

        resultados_yolo = detectar_placas_batch(frames_buffer, yolo)
        ultimo_tuvo_deteccion = any(len(r) > 0 for r in resultados_yolo)

        for idx, recortes in enumerate(resultados_yolo):
            if not recortes:
                continue

            try:
                recortes_np = [r["recorte"] for r in recortes]
                textos = leer_placas_batch(recortes_np, ocr)
            except Exception:
                textos = [leer_placa(r["recorte"], ocr) for r in recortes]

            for rec, numero in zip(recortes, textos):
                if numero is None:
                    continue

                # Hit exacto con set O(1)
                if numero in placas_set:
                    confianza_actual = placas_vistas[numero]["confianza"]
                    es_mejor = len(numero) > len(numero) or (
                        len(numero) == len(numero) and rec["confianza"] > confianza_actual
                    )
                    if es_mejor:
                        datos = placas_vistas[numero]
                        datos.update({
                            "confianza": rec["confianza"],
                            "frame": frame_num - len(frames_buffer) + idx + 1,
                        })
                    continue

                # Verificar similitud con placas existentes
                placa_similar = None
                for guardada in placas_vistas.keys():
                    if es_misma_placa(numero, [guardada]):
                        placa_similar = guardada
                        break

                if placa_similar:
                    confianza_actual = placas_vistas[placa_similar]["confianza"]
                    es_mejor = len(numero) > len(placa_similar) or (
                        len(numero) == len(placa_similar) and rec["confianza"] > confianza_actual
                    )
                    if es_mejor:
                        datos = placas_vistas.pop(placa_similar)
                        info = consultar_placa(numero)
                        datos.update({
                            **info,
                            "placa": numero,
                            "confianza": rec["confianza"],
                        })
                        placas_vistas[numero] = datos
                        placas_set.discard(placa_similar)
                        placas_set.add(numero)
                    continue

                info = consultar_placa(numero)
                guardar_historial(numero, info["estado"])
                placas_vistas[numero] = {
                    **info,
                    "confianza": rec["confianza"],
                    "frame": frame_num - len(frames_buffer) + idx + 1,
                    "timestamp": datetime.now().isoformat(),
                }
                placas_set.add(numero)

    cap.release()

    return {
        "total_frames": frame_num,
        "total_detectadas": len(placas_vistas),
        "placas": list(placas_vistas.values()),
    }


@router.post("/analizar-video")
async def analizar_video(request: Request, video: UploadFile = File(...)):
    _verificar_modelos(request)

    sufijo = Path(video.filename).suffix if video.filename else ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        while True:
            chunk = await video.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
        ruta_tmp = tmp.name

    try:
        resultado = await asyncio.to_thread(
            _procesar_video_sync,
            ruta_tmp,
            request.app.state.yolo,
            request.app.state.ocr,
        )
    finally:
        os.unlink(ruta_tmp)

    if "error" in resultado:
        raise HTTPException(status_code=400, detail=resultado["error"])

    # Broadcast de resultados tras finalizar el procesamiento
    for datos in resultado["placas"]:
        await manager.broadcast({
            "tipo": "deteccion",
            "timestamp": datos.get("timestamp", datetime.now().isoformat()),
            **{k: v for k, v in datos.items() if k not in ("frame",)},
        })

    return {
        "total_frames": resultado["total_frames"],
        "total_detectadas": resultado["total_detectadas"],
        "placas": resultado["placas"],
    }


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.conectar(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.desconectar(ws)
