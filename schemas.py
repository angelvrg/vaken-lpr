"""
TENAX-LPR - Modelos Pydantic
"""

from typing import Optional
from pydantic import BaseModel


class VehiculoCrear(BaseModel):
    placa:  str
    dueno:  Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    color:  Optional[str] = None
    anio:   Optional[int] = None
    estado: Optional[str] = "autorizado"
    # 'autorizado' | 'no_registrado' | 'sospechoso'


class VehiculoEditar(BaseModel):
    dueno:  Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    color:  Optional[str] = None
    anio:   Optional[int] = None
    estado: Optional[str] = None


class CamaraIniciar(BaseModel):
    fuente: Optional[str] = None
    # None = webcam (índice 0), o ruta a IP cam / archivo de video
