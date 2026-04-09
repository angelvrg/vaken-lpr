"""
TENAX-LPR - Procesamiento de imagen y loop de cámara
"""

import asyncio
import os
import re
from datetime import datetime
from difflib import SequenceMatcher

import cv2
import numpy as np
from ultralytics import YOLO
from paddleocr import TextRecognition

from database import consultar_placa, guardar_historial
from websocket import manager

# --- CONFIGURACIÓN OPTIMIZADA PARA VIDEO ---
MOSTRAR_LOGS_OCR = False
GUARDAR_RECORTES = False
CARPETA_RECORTES = "logs_recortes"
# -------------------------------------------

C_VERDE = "\033[92m"
C_AMARILLO = "\033[93m"
C_ROJO = "\033[91m"
C_CIAN = "\033[96m"
C_RESET = "\033[0m"

if GUARDAR_RECORTES:
    os.makedirs(CARPETA_RECORTES, exist_ok=True)

_PATRON_PLACA = re.compile(r'^[A-Z]{2,3}\d{3,4}[A-Z]{0,2}$')


def es_misma_placa(placa_nueva: str, placas_existentes: list, similitud_minima: float = 0.75) -> bool:
    for vista in placas_existentes:
        if SequenceMatcher(None, placa_nueva, vista).ratio() >= similitud_minima:
            return True
    return False


def preprocesar(imagen: np.ndarray) -> np.ndarray:
    imagen_res = cv2.resize(imagen, (128, 32), interpolation=cv2.INTER_CUBIC)
    filtrada = cv2.bilateralFilter(imagen_res, d=9, sigmaColor=75, sigmaSpace=75)
    gris = cv2.cvtColor(filtrada, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)


def detectar_placas(frame: np.ndarray, modelo_yolo: YOLO) -> list[dict]:
    recortes    = []
    # CORRECCIÓN: Quitamos imgsz=320 para que YOLO vuelva a ver en alta definición.
    detecciones = modelo_yolo(frame, verbose=False)
    alto_frame, ancho_frame = frame.shape[:2]

    for det in detecciones:
        for box in det.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confianza = float(box.conf[0])

            if confianza < 0.45:
                continue

            w = x2 - x1
            h = y2 - y1
            margen_x = int(w * 0.08)
            margen_y = int(h * 0.05)
            
            x1_exp = max(0, x1 - margen_x)
            y1_exp = max(0, y1 - margen_y)
            x2_exp = min(ancho_frame, x2 + margen_x)
            y2_exp = min(alto_frame, y2 + margen_y)

            recorte = frame[y1_exp:y2_exp, x1_exp:x2_exp]
            if recorte.size == 0:
                continue

            recortes.append({
                "recorte":   recorte,
                "confianza": round(confianza, 2),
                "bbox":      [x1_exp, y1_exp, x2_exp, y2_exp],
            })

    return recortes


def corregir_lectura(texto: str) -> str:
    if len(texto) < 5:
        return texto

    num_a_letras = {'0': 'O', '1': 'I', '2': 'Z', '4': 'A', '5': 'S', '6': 'G', '8': 'B'}
    caracteres = list(texto)
    
    for i in range(min(2, len(caracteres))):
        if caracteres[i] in num_a_letras:
            caracteres[i] = num_a_letras[caracteres[i]]
            
    if len(caracteres) == 7:
        if caracteres[-1] in num_a_letras and caracteres[-2].isdigit():
            caracteres[-1] = num_a_letras[caracteres[-1]]
            
    return "".join(caracteres)


def leer_placa(recorte: np.ndarray, ocr: TextRecognition) -> str | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    recorte_procesado = preprocesar(recorte)

    try:
        resultados = list(ocr.predict(recorte_procesado))
    except Exception as e:
        if MOSTRAR_LOGS_OCR: print(f"{C_ROJO}Error OCR: {e}{C_RESET}")
        return None

    if not resultados:
        return None

    texto_crudo = ""
    for res in resultados:
        t = ""
        s = 0.0
        if isinstance(res, dict):
            t = res.get("rec_text", "")
            s = res.get("rec_score", 0.0)
            if not t and "rec_texts" in res:
                t = res["rec_texts"][0] if res["rec_texts"] else ""
                s = res["rec_scores"][0] if res["rec_scores"] else 0.0
        else:
            t = getattr(res, "rec_text", "")
            s = getattr(res, "rec_score", 0.0)
            if not t and hasattr(res, "rec_texts"):
                t = res.rec_texts[0] if res.rec_texts else ""
                s = res.rec_scores[0] if res.rec_scores else 0.0

        if s >= 0.35:
            texto_crudo += t

    texto_limpio = "".join(c for c in texto_crudo.upper() if c.isalnum())
    texto_corregido = corregir_lectura(texto_limpio)
    
    if _PATRON_PLACA.match(texto_corregido):
        if MOSTRAR_LOGS_OCR:
            print(f"{C_VERDE}[MATCH VIDEO/CAM] Placa válida encontrada: {texto_corregido}{C_RESET}")
        if GUARDAR_RECORTES:
            cv2.imwrite(f"{CARPETA_RECORTES}/{timestamp}_EXITO_{texto_corregido}.jpg", recorte_procesado)
        return texto_corregido

    if GUARDAR_RECORTES and texto_corregido:
        cv2.imwrite(f"{CARPETA_RECORTES}/{timestamp}_FALLO_{texto_corregido}.jpg", recorte_procesado)
        
    return None


def detectar_y_leer(frame: np.ndarray, modelo_yolo: YOLO, ocr: TextRecognition) -> list[dict]:
    resultados = []
    for rec in detectar_placas(frame, modelo_yolo):
        numero = leer_placa(recorte=rec["recorte"], ocr=ocr)
        if numero is None:
            continue
        resultados.append({
            "placa":     numero,
            "confianza": rec["confianza"],
            "bbox":      rec["bbox"],
        })
    return resultados


async def loop_camara(modelo_yolo: YOLO, ocr: TextRecognition, fuente, stop_event: asyncio.Event):
    cap = cv2.VideoCapture(fuente)

    if not cap.isOpened():
        print(f"{C_ROJO}No se pudo abrir la fuente: {fuente}{C_RESET}")
        return

    placas_recientes = []
    print(f"\n{C_VERDE}=============================================")
    print(f"  CÁMARA INICIADA Y LISTA ({fuente})")
    print(f"============================================={C_RESET}\n")

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            await asyncio.sleep(0.1)
            continue

        detecciones = detectar_y_leer(frame, modelo_yolo, ocr)

        for det in detecciones:
            numero = det["placa"]

            if es_misma_placa(numero, placas_recientes):
                continue

            placas_recientes.append(numero)

            info = consultar_placa(numero)
            guardar_historial(numero, info["estado"])

            print(f"\n{C_VERDE}>>> [NUEVO VEHÍCULO DETECTADO] <<<")
            print(f"Placa  : {numero}")
            print(f"Estado : {info['estado']}")
            print(f"============================================={C_RESET}\n")

            await manager.broadcast({
                "tipo":      "deteccion",
                "timestamp": datetime.now().isoformat(),
                **info,
                "confianza": det["confianza"],
            })

            if len(placas_recientes) > 50:
                placas_recientes.pop(0)

        await asyncio.sleep(0.03)

    cap.release()
    print(f"{C_AMARILLO}Cámara detenida.{C_RESET}")