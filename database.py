"""
TENAX-LPR - Base de datos (PostgreSQL)
"""

from datetime import datetime

import psycopg2
import psycopg2.extras
from psycopg2 import IntegrityError
from psycopg2.pool import ThreadedConnectionPool

from config import DB_CONFIG

_pool = None


def init_pool(minconn=2, maxconn=10):
    """Inicializa el pool de conexiones."""
    global _pool
    _pool = ThreadedConnectionPool(minconn=minconn, maxconn=maxconn, **DB_CONFIG)


def get_conn():
    return _pool.getconn()


def release_conn(conn):
    _pool.putconn(conn)


def iniciar_bd():
    """Crea la tabla historial si no existe."""
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.historial (
                id           SERIAL PRIMARY KEY,
                numero_placa TEXT NOT NULL,
                estado       TEXT NOT NULL,
                timestamp    TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        con.commit()
        cur.close()
    finally:
        release_conn(con)


def consultar_placa(numero: str) -> dict:
    con = get_conn()
    try:
        cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(
            """
            SELECT
                numero_placa,
                (nombre_propietario || ' ' || apellido_paterno || ' ' || COALESCE(apellido_materno, '')) AS dueno,
                marca,
                modelo,
                color,
                anio,
                estatus
            FROM public.vehiculos
            WHERE numero_placa = %s
            """,
            (numero,)
        )
        fila = cur.fetchone()
        cur.close()

        if fila:
            return {
                "placa":  fila["numero_placa"],
                "dueno":  fila["dueno"].strip(),
                "marca":  fila["marca"],
                "modelo": fila["modelo"],
                "color":  fila["color"],
                "anio":   fila["anio"],
                "estado": fila["estatus"],
            }
        else:
            return {
                "placa":  numero,
                "dueno":  "Desconocido",
                "marca":  "Desconocido",
                "modelo": "Desconocido",
                "color":  "Desconocido",
                "anio":   None,
                "estado": "no_registrado",
            }
    finally:
        release_conn(con)


def guardar_historial(placa: str, estado: str):
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO public.historial (numero_placa, estado, timestamp) VALUES (%s, %s, %s)",
            (placa, estado, datetime.now())
        )
        con.commit()
        cur.close()
    finally:
        release_conn(con)
