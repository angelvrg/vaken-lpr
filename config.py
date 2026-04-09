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

# --- CONFIGURACIÓN DE RENDIMIENTO OCR ---
# Hilos de CPU que usará PaddleOCR para inferencia.
# Aumentar este valor mejora la velocidad en máquinas con varios núcleos.
# Recomendado: número de núcleos físicos disponibles (típicamente 4-8).
OCR_CPU_THREADS = 4
