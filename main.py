"""
TENAX-LPR - Backend API
FastAPI + YOLO + OpenCV + PaddleOCR + PostgreSQL
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
from paddleocr import PaddleOCR

from config import MODEL_PATH
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
        app.state.ocr  = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang="en",
        )
        print("Modelos cargados. Usa POST /camara/iniciar para abrir la camara.")
    else:
        app.state.yolo = None
        app.state.ocr  = None
        print(f"Modelo '{MODEL_PATH}' no encontrado. Solo CRUD disponible.")

    yield

    # Al apagar la API, detener camara si estaba activa
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
