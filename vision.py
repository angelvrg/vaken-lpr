# -*- coding: utf-8 -*-
"""
TENAX-LPR - Procesamiento de imagen y loop de camara
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

from config import YOLO_IMGSZ
from database import consultar_placa, guardar_historial
from websocket import manager

# ---------------------------------------------------------------------------
# CONFIGURACION DE DEPURACION
# Cambia a True para activar logs detallados y guardado de recortes.
# ---------------------------------------------------------------------------
MOSTRAR_LOGS_OCR  = False   # Muestra cada paso del pipeline OCR en consola
MOSTRAR_PREVIEW   = False   # Muestra el recorte preprocesado en ASCII en consola
GUARDAR_RECORTES  = False   # Guarda imagenes de recortes en CARPETA_RECORTES
CARPETA_RECORTES  = "logs_recortes"
# ---------------------------------------------------------------------------

C_VERDE    = "\033[92m"
C_AMARILLO = "\033[93m"
C_ROJO     = "\033[91m"
C_CIAN     = "\033[96m"
C_GRIS     = "\033[90m"
C_RESET    = "\033[0m"

if GUARDAR_RECORTES:
    os.makedirs(CARPETA_RECORTES, exist_ok=True)

_PATRON_PLACA = re.compile(r'^[A-Z]{2,3}\d{3,4}[A-Z]{0,2}$')


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def es_misma_placa(placa_nueva: str, placas_existentes: list, similitud_minima: float = 0.60) -> bool:
    if placa_nueva in placas_existentes:
        return True
    for vista in placas_existentes:
        if SequenceMatcher(None, placa_nueva, vista).ratio() >= similitud_minima:
            return True
    return False


def _preview_ascii(imagen: np.ndarray, ancho: int = 40) -> str:
    """Convierte una imagen en representacion ASCII para consola."""
    CHARS = " .:-=+*#%@"
    alto_orig, ancho_orig = imagen.shape[:2]
    alto_nuevo = max(1, int(alto_orig * ancho / ancho_orig / 2))
    pequena = cv2.resize(imagen, (ancho, alto_nuevo))
    if len(pequena.shape) == 3:
        pequena = cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY)
    lineas = []
    for fila in pequena:
        linea = "".join(CHARS[int(p / 256 * len(CHARS))] for p in fila)
        lineas.append(linea)
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# PREPROCESAMIENTO: EL FILTRO DE ORO
# ---------------------------------------------------------------------------

def preprocesar(imagen: np.ndarray) -> np.ndarray:
    # Resize más rápido con INTER_LINEAR (2-3× más veloz que INTER_CUBIC)
    imagen_res = cv2.resize(imagen, (128, 32), interpolation=cv2.INTER_LINEAR)
    filtrada   = cv2.bilateralFilter(imagen_res, d=9, sigmaColor=75, sigmaSpace=75)
    gris       = cv2.cvtColor(filtrada, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)


# ---------------------------------------------------------------------------
# DETECCION YOLO
# ---------------------------------------------------------------------------

def detectar_placas(frame: np.ndarray, modelo_yolo: YOLO) -> list[dict]:
    recortes    = []
    detecciones = modelo_yolo(frame, verbose=False, imgsz=YOLO_IMGSZ)
    alto_frame, ancho_frame = frame.shape[:2]

    if MOSTRAR_LOGS_OCR:
        total_boxes = sum(len(d.boxes) for d in detecciones)
        print(f"{C_GRIS}[YOLO] Boxes crudos detectados: {total_boxes}{C_RESET}")

    for det in detecciones:
        for box in det.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confianza = float(box.conf[0])

            if MOSTRAR_LOGS_OCR:
                estado = "PASA" if confianza >= 0.25 else "DESCARTADO (< 0.25)"
                print(f"{C_GRIS}[YOLO]   box=({x1},{y1},{x2},{y2})  conf={confianza:.2f}  {estado}{C_RESET}")

            if confianza < 0.25:
                continue

            w = x2 - x1
            h = y2 - y1
            
            # Margen conservador del 5% para no aplastar la imagen
            margen_x = int(w * 0.05)
            margen_y = int(h * 0.05)

            x1_exp = max(0, x1 - margen_x)
            y1_exp = max(0, y1 - margen_y)
            x2_exp = min(ancho_frame, x2 + margen_x)
            y2_exp = min(alto_frame, y2 + margen_y)

            recorte = frame[y1_exp:y2_exp, x1_exp:x2_exp]
            if recorte.size == 0:
                if MOSTRAR_LOGS_OCR:
                    print(f"{C_ROJO}[YOLO]   Recorte vacio, se omite.{C_RESET}")
                continue

            recortes.append({
                "recorte":   recorte,
                "confianza": round(confianza, 2),
                "bbox":      [x1_exp, y1_exp, x2_exp, y2_exp],
            })

    if MOSTRAR_LOGS_OCR:
        print(f"{C_GRIS}[YOLO] Recortes que pasan al OCR: {len(recortes)}{C_RESET}")

    return recortes


def detectar_placas_batch(frames: list[np.ndarray], modelo_yolo: YOLO) -> list[list[dict]]:
    """YOLO batch: procesa múltiples frames en una sola llamada."""
    if not frames:
        return []

    detecciones = modelo_yolo(frames, verbose=False, imgsz=YOLO_IMGSZ)
    resultados = []

    for idx, det in enumerate(detecciones):
        recortes = []
        frame = frames[idx]
        alto_frame, ancho_frame = frame.shape[:2]

        for box in det.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confianza = float(box.conf[0])

            if confianza < 0.25:
                continue

            w = x2 - x1
            h = y2 - y1

            margen_x = int(w * 0.05)
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

        resultados.append(recortes)

    return resultados


# ---------------------------------------------------------------------------
# CORRECCION DE CARACTERES
# ---------------------------------------------------------------------------

def corregir_lectura(texto: str) -> str:
    if len(texto) < 5:
        return texto

    num_a_letras = {'0': 'O', '1': 'I', '2': 'Z', '4': 'A', '5': 'S', '6': 'G', '8': 'B'}
    caracteres = list(texto)

    for i in range(min(2, len(caracteres))):
        if caracteres[i] in num_a_letras:
            nueva = num_a_letras[caracteres[i]]
            if i == 0 or caracteres[i - 1] != nueva:
                if MOSTRAR_LOGS_OCR:
                    print(f"{C_GRIS}[CORRECCION] pos {i}: '{caracteres[i]}' -> '{nueva}'{C_RESET}")
                caracteres[i] = nueva
            else:
                if MOSTRAR_LOGS_OCR:
                    print(f"{C_GRIS}[CORRECCION] pos {i}: '{caracteres[i]}' eliminado "
                          f"(seria duplicado de '{caracteres[i - 1]}'){C_RESET}")
                caracteres[i] = ""

    caracteres = [c for c in caracteres if c != ""]

    if len(caracteres) == 7:
        if caracteres[-1] in num_a_letras and caracteres[-2].isdigit():
            if MOSTRAR_LOGS_OCR:
                print(f"{C_GRIS}[CORRECCION] ultimo char: '{caracteres[-1]}' -> "
                      f"'{num_a_letras[caracteres[-1]]}'{C_RESET}")
            caracteres[-1] = num_a_letras[caracteres[-1]]

    return "".join(caracteres)


# ---------------------------------------------------------------------------
# LECTURA OCR
# ---------------------------------------------------------------------------

def _extraer_texto_y_score(res) -> tuple[str, float]:
    """Extrae texto y score de un resultado de PaddleOCR v3."""
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
    return t, s


def leer_placas_batch(recortes: list[np.ndarray], ocr: TextRecognition) -> list[str | None]:
    """OCR en batch: procesa múltiples recortes en una sola llamada a predict()."""
    if not recortes:
        return []

    procesados = [preprocesar(r) for r in recortes]

    try:
        batch_salida = list(ocr.predict(procesados))
    except Exception as e:
        if MOSTRAR_LOGS_OCR:
            print(f"{C_ROJO}[OCR] Error en predict() batch: {e}{C_RESET}")
        raise

    # Normalizar formato de salida de Paddle (a veces anida resultados)
    if len(batch_salida) == 1 and len(recortes) > 1:
        unico = batch_salida[0]
        if isinstance(unico, (list, tuple)):
            batch_salida = unico

    if len(batch_salida) != len(recortes):
        raise ValueError(
            f"Mismatch batch: {len(batch_salida)} resultados para {len(recortes)} recortes"
        )

    resultados: list[str | None] = []
    for salida_img in batch_salida:
        texto_crudo = ""
        items = salida_img if isinstance(salida_img, (list, tuple)) else [salida_img]
        for res in items:
            t, s = _extraer_texto_y_score(res)
            if s >= 0.35:
                texto_crudo += t

        texto_limpio = "".join(c for c in texto_crudo.upper() if c.isalnum())
        texto_corregido = corregir_lectura(texto_limpio)

        if _PATRON_PLACA.match(texto_corregido):
            resultados.append(texto_corregido)
        else:
            resultados.append(None)

    return resultados


def leer_placa(recorte: np.ndarray, ocr: TextRecognition) -> str | None:
    timestamp         = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    recorte_procesado = preprocesar(recorte)

    if MOSTRAR_LOGS_OCR:
        print(f"\n{C_CIAN}[OCR] Iniciando lectura  timestamp={timestamp}{C_RESET}")
        print(f"{C_GRIS}[OCR] Tamano recorte preprocesado: {recorte_procesado.shape}{C_RESET}")

    if MOSTRAR_PREVIEW:
        print(f"{C_GRIS}[PREVIEW] Recorte preprocesado:{C_RESET}")
        print(_preview_ascii(recorte_procesado))

    try:
        resultados = list(ocr.predict(recorte_procesado))
    except Exception as e:
        if MOSTRAR_LOGS_OCR:
            print(f"{C_ROJO}[OCR] Error en predict(): {e}{C_RESET}")
        return None

    if not resultados:
        if MOSTRAR_LOGS_OCR:
            print(f"{C_AMARILLO}[OCR] predict() devolvio lista vacia.{C_RESET}")
        return None

    texto_crudo = ""
    for i, res in enumerate(resultados):
        t, s = _extraer_texto_y_score(res)

        if MOSTRAR_LOGS_OCR:
            estado = "ACEPTA" if s >= 0.35 else "DESCARTA (score < 0.35)"
            print(f"{C_GRIS}[OCR]   resultado[{i}]: texto='{t}'  score={s:.3f}  -> {estado}{C_RESET}")

        # Umbral equilibrado a 0.35 para captar texto claro sin alucinar ruido
        if s >= 0.35:
            texto_crudo += t

    texto_limpio    = "".join(c for c in texto_crudo.upper() if c.isalnum())
    texto_corregido = corregir_lectura(texto_limpio)

    if MOSTRAR_LOGS_OCR:
        print(f"{C_GRIS}[OCR] crudo='{texto_crudo}'  limpio='{texto_limpio}'  corregido='{texto_corregido}'{C_RESET}")
        print(f"{C_GRIS}[OCR] Patron valido: {bool(_PATRON_PLACA.match(texto_corregido))}{C_RESET}")

    if _PATRON_PLACA.match(texto_corregido):
        if MOSTRAR_LOGS_OCR:
            print(f"{C_VERDE}[OCR] Placa valida: {texto_corregido}{C_RESET}")
        if GUARDAR_RECORTES:
            ruta = f"{CARPETA_RECORTES}/{timestamp}_EXITO_{texto_corregido}.jpg"
            cv2.imwrite(ruta, recorte_procesado)
            if MOSTRAR_LOGS_OCR:
                print(f"{C_GRIS}[OCR] Recorte guardado -> {ruta}{C_RESET}")
        return texto_corregido

    if MOSTRAR_LOGS_OCR:
        print(f"{C_AMARILLO}[OCR] No coincide con patron: '{texto_corregido}'{C_RESET}")
    if GUARDAR_RECORTES and texto_corregido:
        ruta = f"{CARPETA_RECORTES}/{timestamp}_FALLO_{texto_corregido}.jpg"
        cv2.imwrite(ruta, recorte_procesado)
        if MOSTRAR_LOGS_OCR:
            print(f"{C_GRIS}[OCR] Recorte de fallo guardado -> {ruta}{C_RESET}")

    return None


# ---------------------------------------------------------------------------
# PIPELINE PRINCIPAL
# ---------------------------------------------------------------------------

def detectar_y_leer(frame: np.ndarray, modelo_yolo: YOLO, ocr: TextRecognition) -> list[dict]:
    recortes = detectar_placas(frame, modelo_yolo)
    if not recortes:
        return []

    # Batch OCR para reducir overhead de inferencia (30-60% más rápido)
    try:
        recortes_np = [r["recorte"] for r in recortes]
        textos = leer_placas_batch(recortes_np, ocr)
    except Exception as e:
        if MOSTRAR_LOGS_OCR:
            print(f"{C_ROJO}[OCR] Fallback a individual por error batch: {e}{C_RESET}")
        textos = [leer_placa(r["recorte"], ocr) for r in recortes]

    resultados = []
    for rec, numero in zip(recortes, textos):
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
    print(f"  CAMARA INICIADA Y LISTA ({fuente})")
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
                if MOSTRAR_LOGS_OCR:
                    print(f"{C_GRIS}[CAMARA] Placa '{numero}' ya registrada recientemente, se omite.{C_RESET}")
                continue

            placas_recientes.append(numero)

            info = consultar_placa(numero)
            guardar_historial(numero, info["estado"])

            print(f"\n{C_VERDE}>>> [NUEVO VEHICULO DETECTADO] <<<")
            print(f"Placa    : {numero}")
            print(f"Estado   : {info['estado']}")
            print(f"Confianza: {det['confianza']}")
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
    print(f"{C_AMARILLO}Camara detenida.{C_RESET}")
