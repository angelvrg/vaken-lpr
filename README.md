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
cd vaken-lpr
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

> **Importante:** usa exactamente `paddlepaddle==3.2.0`. La versión 3.3.0 de paddlepaddle causa un error `NotImplementedError` en oneDNN y el sistema no arranca.

### 4. Configurar la base de datos

Crea la base de datos en PostgreSQL:

```sql
CREATE DATABASE tenax_lpr;
```

Luego abre `config.py` y ajusta los datos de conexión:

```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "tenax_lpr",
    "user":     "postgres",
    "password": "tu_contraseña",
}
```

> La tabla `historial` se crea automáticamente al iniciar el servidor. La tabla `vehiculos` debe existir previamente con la estructura esperada.

### 5. Colocar el modelo YOLO

Coloca el archivo `modelo_placas.pt` en la raíz del proyecto, junto a `main.py`.

### 6. Iniciar el servidor

```bash
python main.py
```

La API queda disponible en `http://localhost:8000`.  
La documentación interactiva (Swagger) en `http://localhost:8000/docs`.

---

## Estructura del proyecto

```
vaken-lpr/
├── main.py               # Punto de entrada, carga de modelos, lifespan
├── config.py             # Configuración global (rutas, BD)
├── database.py           # Conexión PostgreSQL y queries
├── schemas.py            # Modelos Pydantic
├── vision.py             # Pipeline YOLO + preprocesamiento + OCR
├── websocket.py          # Manager de conexiones WebSocket
├── modelo_placas.pt      # Modelo YOLO entrenado (no incluido en repo)
├── routes/
│   ├── consulta.py       # GET / · GET /placa/{numero} · GET /historial
│   ├── vehiculos.py      # CRUD /vehiculos
│   └── camara.py         # Cámara en vivo, análisis de media, WebSocket
└── docs/
    └── API.md            # Referencia completa de la API
```

---

## Esquema de la base de datos

### Tabla `public.vehiculos` (debe existir previamente)

```
id                  SERIAL PRIMARY KEY
numero_placa        TEXT
nombre_propietario  TEXT
apellido_paterno    TEXT
apellido_materno    TEXT
marca               TEXT
modelo              TEXT
color               TEXT
anio                INTEGER
estatus             TEXT   -- 'autorizado' | 'sospechoso' | 'no_registrado'
fecha_registro      TIMESTAMP
```

### Tabla `public.historial` (se crea automáticamente)

```
id           SERIAL PRIMARY KEY
numero_placa TEXT
estado       TEXT
timestamp    TIMESTAMP
```

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

Consulta [`docs/API.md`](docs/API.md) para la referencia completa de todos los endpoints, parámetros, esquemas de respuesta y códigos de estado.

---

## Pipeline de detección

```
Cámara / Imagen / Video
        ↓
   YOLO (detección de placa, umbral 0.25)
        ↓
   OpenCV (recorte + margen 5%)
        ↓
   Preprocesamiento (resize 128×32, filtro bilateral, escala de grises)
        ↓
   PaddleOCR TextRecognition (en_PP-OCRv4_mobile_rec)
        ↓
   Corrección de caracteres + validación regex
        ↓
   Consulta PostgreSQL → clasifica: autorizado / sospechoso / no_registrado
        ↓
   WebSocket → React dashboard
```

---

## Notas sobre PaddleOCR v3

PaddleOCR 3.x reemplazó la clase `PaddleOCR` anterior por una API basada en pipelines (`TextRecognition`, `TextDetection`, `TextSystem`). Este proyecto usa `TextRecognition` directamente para reconocimiento de caracteres alfanuméricos en placas vehiculares.

### Parámetros eliminados en PaddleOCR v3

Los siguientes parámetros ya no existen y no deben usarse:

- `use_angle_cls` — eliminado; no necesario con `TextRecognition` directo
- `lang` — eliminado del constructor; seleccionar modelo por `model_name`
- `det_limit_side_len` — eliminado; controlar tamaño antes de llamar a `predict()`
- `rec_batch_num` — eliminado; `predict()` acepta lista de imágenes directamente
- `enable_mkldnn` — eliminado; MKL-DNN se activa internamente de forma automática
- `use_gpu` — eliminado; seleccionar device al inicializar PaddlePaddle
- `cls_thresh` — eliminado; componente de clasificación es ahora un objeto separado

### Formato de respuesta de `predict()`

`TextRecognition.predict()` devuelve una lista de dicts con las claves `rec_text` y `rec_score` (singular). Este formato es distinto al de `PaddleOCR.predict()`, que devuelve `rec_texts` y `rec_scores` (listas). No son intercambiables.

---

## Notas generales

- Los números de placa siempre se almacenan y devuelven en **mayúsculas**.
- La cámara **no se inicia automáticamente** al arrancar el servidor. Usa `POST /camara/iniciar`.
- Las detecciones en tiempo real se propagan a **todos** los clientes WebSocket conectados.
- La autenticación no está implementada en esta versión.