"""
TENAX-LPR - Procesamiento de imagen y loop de cámara
"""

import asyncio
import re
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO
from paddleocr import PaddleOCR

from database import consultar_placa, guardar_historial
from websocket import manager


# Regex para validar formato de placa mexicana (ej: GD7149D, GXX0000, ABC123D)
_PATRON_PLACA = re.compile(r'^[A-Z]{2,3}\d{3,4}[A-Z]{0,2}$')


def preprocesar(imagen: np.ndarray) -> np.ndarray:
    # redimensionar a tamaño óptimo para PaddleOCR
    imagen = cv2.resize(imagen, (128, 32), interpolation=cv2.INTER_CUBIC)
    # filtro bilateral: reduce ruido preservando bordes del texto
    filtrada = cv2.bilateralFilter(imagen, d=9, sigmaColor=75, sigmaSpace=75)
    gris = cv2.cvtColor(filtrada, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)


def detectar_placas(frame: np.ndarray, modelo_yolo: YOLO) -> list[dict]:
    """Solo YOLO: devuelve los recortes de placas detectadas sin pasar al OCR."""
    recortes   = []
    detecciones = modelo_yolo(frame, verbose=False)

    for det in detecciones:
        for box in det.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confianza = float(box.conf[0])

            if confianza < 0.5:
                continue

            recorte = frame[y1:y2, x1:x2]
            if recorte.size == 0:
                continue

            recortes.append({
                "recorte":   recorte,
                "confianza": round(confianza, 2),
                "bbox":      [x1, y1, x2, y2],
            })

    return recortes


def leer_placa(recorte: np.ndarray, ocr: PaddleOCR) -> str | None:
    """Solo OCR: recibe un recorte de placa y devuelve el texto o None."""
    recorte_procesado = preprocesar(recorte)

    resultado_ocr = ocr.predict(recorte_procesado)
    if not resultado_ocr or not resultado_ocr[0]:
        return None

    texto  = ""
    res    = resultado_ocr[0]
    textos = res.get("rec_texts", [])
    scores = res.get("rec_scores", [])
    for t, s in zip(textos, scores):
        if s >= 0.6:
            texto += t

    texto_limpio = "".join(c for c in texto.upper() if c.isalnum())

    if not _PATRON_PLACA.match(texto_limpio):
        return None

    return texto_limpio



    resultados  = []
    detecciones = modelo_yolo(frame, verbose=False)

    for det in detecciones:
        for box in det.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confianza = float(box.conf[0])

            if confianza < 0.5:
                continue

            recorte = frame[y1:y2, x1:x2]
            if recorte.size == 0:
                continue

            recorte_procesado = preprocesar(recorte)

            resultado_ocr = ocr.predict(recorte_procesado)
            if not resultado_ocr or not resultado_ocr[0]:
                continue

            texto = ""
            res = resultado_ocr[0]
            textos = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            for t, s in zip(textos, scores):
                if s >= 0.6:
                    texto += t

            texto_limpio = "".join(c for c in texto.upper() if c.isalnum())

            # validar con regex que coincida con formato de placa mexicana
            if not _PATRON_PLACA.match(texto_limpio):
                continue

            resultados.append({
                "placa":     texto_limpio,
                "confianza": round(confianza, 2),
                "bbox":      [x1, y1, x2, y2]
            })

    return resultados


def detectar_y_leer(frame: np.ndarray, modelo_yolo: YOLO, ocr: PaddleOCR) -> list[dict]:
    """YOLO + OCR combinados. Usado por analizar_imagen y loop_camara."""
    resultados = []
    for rec in detectar_placas(frame, modelo_yolo):
        numero = leer_placa(rec["recorte"], ocr)
        if numero is None:
            continue
        resultados.append({
            "placa":     numero,
            "confianza": rec["confianza"],
            "bbox":      rec["bbox"],
        })
    return resultados


(modelo_yolo: YOLO, ocr: PaddleOCR, fuente, stop_event: asyncio.Event):
    cap = cv2.VideoCapture(fuente)

    if not cap.isOpened():
        print(f"No se pudo abrir la fuente: {fuente}")
        return

    placas_recientes = set()
    print(f"Camara iniciada: {fuente}")

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            await asyncio.sleep(0.1)
            continue

        detecciones = detectar_y_leer(frame, modelo_yolo, ocr)

        for det in detecciones:
            numero = det["placa"]

            if numero in placas_recientes:
                continue

            placas_recientes.add(numero)

            info = consultar_placa(numero)
            guardar_historial(numero, info["estado"])

            print(f"Deteccion: {numero} | estado: {info['estado']}")

            await manager.broadcast({
                "tipo":      "deteccion",
                "timestamp": datetime.now().isoformat(),
                **info,
                "confianza": det["confianza"],
            })

            if len(placas_recientes) > 50:
                placas_recientes.clear()

        await asyncio.sleep(0.03)  # ~30 fps

    cap.release()
    print("Camara detenida.")
