"""
TENAX-LPR - Endpoints CRUD de vehículos
"""

from fastapi import APIRouter, HTTPException
from psycopg2 import IntegrityError
import psycopg2.extras

from database import get_conn
from schemas import VehiculoCrear, VehiculoEditar

router = APIRouter(prefix="/vehiculos")

ESTADOS_VALIDOS = {"autorizado", "no_registrado", "sospechoso"}


@router.get("")
def listar_vehiculos(limit: int = 100, offset: int = 0):
    con = get_conn()
    cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        """
        SELECT
            id,
            numero_placa      AS placa,
            nombre_propietario AS dueno,
            marca,
            modelo,
            color,
            anio,
            estatus           AS estado
        FROM public.vehiculos
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset)
    )
    filas = cur.fetchall()
    cur.close()
    con.close()
    return [dict(f) for f in filas]


@router.post("", status_code=201)
def crear_vehiculo(datos: VehiculoCrear):
    if datos.estado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estado invalido. Valores permitidos: {ESTADOS_VALIDOS}"
        )

    con = get_conn()
    cur = con.cursor()
    try:
        cur.execute(
            """
            INSERT INTO public.vehiculos
                (numero_placa, nombre_propietario, marca, modelo, color, anio, estatus)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                datos.placa.upper(),
                datos.dueno,
                datos.marca,
                datos.modelo,
                datos.color,
                datos.anio,
                datos.estado,
            )
        )
        nuevo_id = cur.fetchone()[0]
        con.commit()
    except IntegrityError:
        con.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"La placa '{datos.placa.upper()}' ya existe en la base de datos."
        )
    finally:
        cur.close()
        con.close()

    return {"mensaje": "Vehiculo registrado correctamente.", "id": nuevo_id, "placa": datos.placa.upper()}


@router.patch("/{numero}")
def editar_vehiculo(numero: str, datos: VehiculoEditar):
    if datos.estado is not None and datos.estado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estado invalido. Valores permitidos: {ESTADOS_VALIDOS}"
        )

    mapeo_campos = {
        "dueno":  "nombre_propietario",
        "marca":  "marca",
        "modelo": "modelo",
        "color":  "color",
        "anio":   "anio",
        "estado": "estatus",
    }

    campos = {}
    for campo_pydantic, valor in datos.model_dump(exclude_none=True).items():
        columna = mapeo_campos.get(campo_pydantic)
        if columna:
            campos[columna] = valor

    if not campos:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar.")

    set_clause = ", ".join(f"{col} = %s" for col in campos)
    valores    = list(campos.values()) + [numero.upper()]

    con = get_conn()
    cur = con.cursor()
    cur.execute(
        f"UPDATE public.vehiculos SET {set_clause} WHERE numero_placa = %s",
        valores
    )
    con.commit()
    afectadas = cur.rowcount
    cur.close()
    con.close()

    if afectadas == 0:
        raise HTTPException(status_code=404, detail=f"Placa '{numero.upper()}' no encontrada.")

    return {"mensaje": "Vehiculo actualizado correctamente.", "placa": numero.upper()}


@router.delete("/{numero}")
def eliminar_vehiculo(numero: str):
    con = get_conn()
    cur = con.cursor()
    cur.execute(
        "DELETE FROM public.vehiculos WHERE numero_placa = %s",
        (numero.upper(),)
    )
    con.commit()
    afectadas = cur.rowcount
    cur.close()
    con.close()

    if afectadas == 0:
        raise HTTPException(status_code=404, detail=f"Placa '{numero.upper()}' no encontrada.")

    return {"mensaje": "Vehiculo eliminado correctamente.", "placa": numero.upper()}
