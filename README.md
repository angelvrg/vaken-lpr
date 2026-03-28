# vaken-lpr
Backend del sistema de reconocimiento de placas vehiculares

Detecta placas en imágenes, video y cámara en vivo usando YOLO + PaddleOCR, consulta una base de datos PostgreSQL y transmite los resultados en tiempo real por WebSocket a un dashboard en React.

---

## Requisitos del sistema

- Python **3.9 – 3.13** (no compatible con 3.14+)
- PostgreSQL **16**
- Git

---

## Instalación del backend

### 1. Clonar el repositorio

```bash
git clone https://github.com/angelvrg/vaken-lpr.git
cd tenax-lpr/backend
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install fastapi uvicorn[standard] psycopg2-binary python-multipart
pip install ultralytics opencv-python
pip install paddlepaddle==3.2.0
pip install paddleocr==3.3.0
```

> **Importante:** usa exactamente `paddlepaddle==3.2.0`. La versión 3.3.0 causa un error de `NotImplementedError` en oneDNN y el sistema no arranca.

### 4. Configurar la base de datos

Crea la base de datos en PostgreSQL:

```sql
CREATE DATABASE tenax_lpr;
```

Luego abre `backend/config.py` y ajusta los datos de conexión:

```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "tenax_lpr",
    "user":     "postgres",
    "password": "tu_contraseña",
}
```

### 5. Colocar el modelo YOLO

Coloca el archivo `modelo_placas.pt` dentro de la carpeta `backend/`, junto a `main.py`.

### 6. Iniciar el servidor

```bash
python main.py
```

La API queda disponible en `http://localhost:8000`.  
La documentación interactiva (Swagger) en `http://localhost:8000/docs`.

---

## Endpoints disponibles

### Consulta
- `GET /` — Estado del sistema y la cámara
- `GET /placa/{numero}` — Consultar una placa en la base de datos
- `GET /historial` — Últimos registros de acceso

### Vehículos (CRUD)
- `GET /vehiculos` — Listar vehículos
- `POST /vehiculos` — Registrar vehículo
- `PATCH /vehiculos/{numero}` — Editar vehículo
- `DELETE /vehiculos/{numero}` — Eliminar vehículo

### Cámara y análisis
- `POST /camara/iniciar` — Iniciar cámara en vivo
- `POST /camara/detener` — Detener cámara
- `POST /analizar-imagen` — Analizar una imagen (multipart/form-data)
- `POST /analizar-video` — Analizar un video completo

### WebSocket
- `WS /ws` — Recibe detecciones en tiempo real