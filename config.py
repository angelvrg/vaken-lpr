"""
TENAX-LPR - Configuración global
"""

MODEL_PATH = "modelo_placas.pt"
CAMARA     = 0  # 0 = cámara integrada, o ruta a video / IP cam

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "tenax_lpr",
    "user":     "postgres",
    "password": "admin-A1",  # cambia si tu contraseña es diferente
}
