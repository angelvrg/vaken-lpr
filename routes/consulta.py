"""
TENAX-LPR - Endpoints de consulta general
"""

from fastapi import APIRouter, Request

import psycopg2.extras
from database import get_conn, consultar_placa

router = APIRouter()


@router.get("/")
def raiz(request: Request):
    camara_estado = "sin modelo"
    if request.app.state.yolo is not None:
        camara_estado = (
            "activa"
            if request.app.state.camara_task and not request.app.state.camara_task.done()
            else "detenida"
        )
    return {
        "sistema": "TENAX-LPR",
        "estado":  "activo",
        "camara":  camara_estado,
    }


@router.get("/placa/{numero}")
def buscar_placa(numero: str):
    return consultar_placa(numero.upper())


@router.get("/historial")
def obtener_historial(limit: int = 50):
    con = get_conn()
    cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT numero_placa AS placa, estado, timestamp FROM public.historial ORDER BY id DESC LIMIT %s",
        (limit,)
    )
    filas = cur.fetchall()
    cur.close()
    con.close()
    return [
        {
            "placa":     f["placa"],
            "estado":    f["estado"],
            "timestamp": f["timestamp"].isoformat() if hasattr(f["timestamp"], "isoformat") else f["timestamp"],
        }
        for f in filas
    ]
