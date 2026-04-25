"""
TENAX-LPR - Configuración global
"""

MODEL_PATH = "modelo_placas.pt"
CAMARA     = 0  # 0 = cámara integrada, o ruta a video / IP cam

# Optimización de inferencia
YOLO_DEVICE = "auto"   # 'auto', 'cuda', 'cpu'
YOLO_IMGSZ  = 640
OCR_CPU_THREADS = 4

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "tenax_lpr",
    "user":     "postgres",
    "password": "admin-A1",  # cambia si tu contraseña es diferente
}

