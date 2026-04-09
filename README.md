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

## Documentación completa de la API

Consulta [`docs/API.md`](docs/API.md) para ver la referencia detallada de todos los endpoints,
parámetros, cuerpos de petición, esquemas de respuesta y códigos de estado.

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

---

## Optimización de velocidad — PaddleOCR v3

PaddleOCR 3.x eliminó muchos parámetros de la clase `PaddleOCR` anterior y los reemplazó
por una API basada en pipelines (`TextRecognition`, `TextDetection`, `TextSystem`).
Las mejoras implementadas en este proyecto son:

### 1. Procesamiento en batch (mayor impacto)

La función `detectar_y_leer()` ahora recolecta **todos los recortes** de un frame y
los envía en **una sola llamada** a `ocr.predict([img1, img2, ...])`.

```
# Antes (v anterior): N recortes → N llamadas OCR
for recorte in recortes:
    leer_placa(recorte, ocr)   # una llamada por recorte

# Ahora: N recortes → 1 llamada OCR
ocr.predict([recorte1, recorte2, ...])  # batch
```

Esto elimina la sobrecarga de inicialización de inferencia por cada recorte, reduciendo
la latencia total entre 30 % y 60 % cuando hay varios vehículos en pantalla.

### 2. Número de hilos de CPU

En `config.py` se puede ajustar `OCR_CPU_THREADS` (por defecto `4`).
Este valor se pasa al constructor `TextRecognition(cpu_num_threads=N)` y controla
cuántos hilos usa Paddle para la inferencia en CPU.

```python
# config.py
OCR_CPU_THREADS = 4   # ajusta según los núcleos físicos de tu máquina
```

### 3. Modelo ligero preseleccionado

Se usa `en_PP-OCRv4_mobile_rec`, el modelo de reconocimiento más rápido disponible en
PaddleOCR v3 para caracteres latinos/alfanuméricos, con una relación velocidad/precisión
óptima para placas vehiculares.

### 4. Preprocesado fijo a 128×32 px

La función `preprocesar()` redimensiona cada recorte a `128×32` px antes del OCR.
Este tamaño coincide con el input esperado por los modelos `PP-OCRv4_rec`, por lo que
Paddle no necesita escalar internamente, ahorrando tiempo adicional.

### Parámetros eliminados en PaddleOCR v3

Los siguientes parámetros ya **no existen** en la nueva API y no deben usarse:

| Parámetro antiguo      | Estado en v3         | Alternativa                                    |
|------------------------|----------------------|------------------------------------------------|
| `use_angle_cls`        | Eliminado            | No necesario con `TextRecognition` directo     |
| `lang`                 | Eliminado del constructor | Seleccionar modelo por `model_name`        |
| `det_limit_side_len`   | Eliminado            | Controlar tamaño antes de llamar a `predict()` |
| `rec_batch_num`        | Eliminado            | `predict()` acepta lista de imágenes directamente |
| `enable_mkldnn`        | Eliminado            | Controlado internamente por Paddle             |
| `use_gpu`              | Eliminado            | Seleccionar device al inicializar PaddlePaddle |
| `cls_thresh`           | Eliminado            | Componente de clasificación separado           |
