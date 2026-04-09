"""
TENAX-LPR - Backend API
FastAPI + YOLO + OpenCV + PaddleOCR + PostgreSQL
"""

import os
import logging

# Silenciar todos los sistemas de log de Paddle antes de importar
os.environ["DISABLE_AUTO_LOGGING_CONFIG"] = "1"
os.environ["PADDLE_PDX_LOG_LEVEL"] = "ERROR"

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
from paddleocr import TextRecognition, logger

# Asegurar niveles de log por si acaso
logger.setLevel(logging.ERROR)
for name in ("paddlex", "paddle", "ppocr"):
    logging.getLogger(name).setLevel(logging.ERROR)

from config import MODEL_PATH, OCR_CPU_THREADS
from database import iniciar_bd
from routes.consulta import router as router_consulta
from routes.vehiculos import router as router_vehiculos
from routes.camara import router as router_camara


@asynccontextmanager
async def lifespan(app: FastAPI):
    iniciar_bd()

    app.state.camara_task = None
    app.state.camara_stop = None

    if Path(MODEL_PATH).exists():
        app.state.yolo = YOLO(MODEL_PATH)

        # Modelo ultra rápido nativo en inglés.
        # cpu_num_threads: incrementa la paralelización en CPU para mayor velocidad.
        app.state.ocr = TextRecognition(
            model_name="en_PP-OCRv4_mobile_rec",
            cpu_num_threads=OCR_CPU_THREADS,
        )

        print("Modelos cargados. Usa POST /camara/iniciar para abrir la camara.")
    else:
        app.state.yolo = None
        app.state.ocr  = None
        print(f"Modelo '{MODEL_PATH}' no encontrado. Solo CRUD disponible.")

    yield

    if app.state.camara_stop is not None:
        app.state.camara_stop.set()


app = FastAPI(title="TENAX-LPR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_consulta)
app.include_router(router_vehiculos)
app.include_router(router_camara)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)