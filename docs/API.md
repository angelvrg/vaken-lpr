# TENAX-LPR — Documentación de la API

**Base URL:** `http://localhost:8000`  
**Versión:** 1.0  
**Framework:** FastAPI · Python 3.9-3.13

> La documentación interactiva (Swagger UI) también está disponible en tiempo de ejecución en:  
> `http://localhost:8000/docs`  
> `http://localhost:8000/redoc`

---

## Índice

1. [Estado del sistema](#1-estado-del-sistema)
2. [Consulta de placas e historial](#2-consulta-de-placas-e-historial)
3. [Vehículos — CRUD](#3-vehículos--crud)
4. [Cámara en vivo](#4-cámara-en-vivo)
5. [Análisis de imágenes y vídeos](#5-análisis-de-imágenes-y-vídeos)
6. [WebSocket — detecciones en tiempo real](#6-websocket--detecciones-en-tiempo-real)
7. [Esquemas Pydantic](#7-esquemas-pydantic)
8. [Códigos de estado HTTP comunes](#8-códigos-de-estado-http-comunes)

---

## 1. Estado del sistema

### `GET /`

Devuelve el estado general del servidor y de la cámara.

**No requiere cuerpo ni parámetros.**

#### Respuesta exitosa — `200 OK`

```json
{
  "sistema": "TENAX-LPR",
  "estado": "activo",
  "camara": "detenida"
}
```

| Campo     | Tipo   | Descripción                                               |
|-----------|--------|-----------------------------------------------------------|
| `sistema` | string | Nombre del sistema                                        |
| `estado`  | string | Siempre `"activo"` mientras el servidor esté en línea     |
| `camara`  | string | `"activa"` · `"detenida"` · `"sin modelo"` |

---

## 2. Consulta de placas e historial

### `GET /placa/{numero}`

Consulta los datos del vehículo registrado con esa placa.

| Parámetro | Ubicación | Tipo   | Requerido | Descripción                    |
|-----------|-----------|--------|-----------|--------------------------------|
| `numero`  | path      | string | ✅        | Número de placa (se convierte a mayúsculas automáticamente) |

#### Respuesta exitosa — `200 OK`

```json
{
  "placa":  "ABC1234",
  "dueno":  "Juan Pérez González",
  "marca":  "Toyota",
  "modelo": "Corolla",
  "color":  "Blanco",
  "anio":   2020,
  "estado": "autorizado"
}
```

| Campo    | Tipo        | Descripción                                                                 |
|----------|-------------|-----------------------------------------------------------------------------|
| `placa`  | string      | Número de placa                                                             |
| `dueno`  | string      | Nombre completo del propietario (`"Desconocido"` si no está registrado)     |
| `marca`  | string      | Marca del vehículo                                                          |
| `modelo` | string      | Modelo del vehículo                                                         |
| `color`  | string      | Color del vehículo                                                          |
| `anio`   | int · null  | Año del vehículo                                                            |
| `estado` | string      | `"autorizado"` · `"sospechoso"` · `"no_registrado"`                         |

> **Nota:** Si la placa no existe en la base de datos, se devuelven `200 OK` con todos los campos en `"Desconocido"` y `estado: "no_registrado"`. No se lanza `404`.

---

### `GET /historial`

Devuelve los últimos registros de acceso detectados por el sistema.

| Parámetro | Ubicación | Tipo | Requerido | Por defecto | Descripción                      |
|-----------|-----------|------|-----------|-------------|----------------------------------|
| `limit`   | query     | int  | ❌        | `50`        | Número máximo de registros a devolver |

#### Respuesta exitosa — `200 OK`

```json
[
  {
    "placa":     "ABC1234",
    "estado":    "autorizado",
    "timestamp": "2025-06-01T10:32:05.123456"
  },
  {
    "placa":     "XYZ9999",
    "estado":    "sospechoso",
    "timestamp": "2025-06-01T10:30:11.000000"
  }
]
```

| Campo       | Tipo   | Descripción                                  |
|-------------|--------|----------------------------------------------|
| `placa`     | string | Número de placa detectada                    |
| `estado`    | string | Estado en el momento de la detección         |
| `timestamp` | string | Fecha y hora en formato ISO 8601             |

---

## 3. Vehículos — CRUD

Todos los endpoints de este grupo tienen el prefijo `/vehiculos`.

---

### `GET /vehiculos`

Lista todos los vehículos registrados en la base de datos.

| Parámetro | Ubicación | Tipo | Requerido | Por defecto | Descripción                        |
|-----------|-----------|------|-----------|-------------|------------------------------------|
| `limit`   | query     | int  | ❌        | `100`       | Máximo de registros a devolver     |
| `offset`  | query     | int  | ❌        | `0`         | Desplazamiento para paginación     |

#### Respuesta exitosa — `200 OK`

```json
[
  {
    "id":     1,
    "placa":  "ABC1234",
    "dueno":  "Juan Pérez",
    "marca":  "Toyota",
    "modelo": "Corolla",
    "color":  "Blanco",
    "anio":   2020,
    "estado": "autorizado"
  }
]
```

---

### `POST /vehiculos`

Registra un nuevo vehículo en la base de datos.

#### Cuerpo de la petición — `application/json`

```json
{
  "placa":  "DEF5678",
  "dueno":  "María López",
  "marca":  "Honda",
  "modelo": "Civic",
  "color":  "Negro",
  "anio":   2022,
  "estado": "autorizado"
}
```

| Campo    | Tipo        | Requerido | Por defecto   | Descripción                                                      |
|----------|-------------|-----------|---------------|------------------------------------------------------------------|
| `placa`  | string      | ✅        | —             | Número de placa (se guarda en mayúsculas)                        |
| `dueno`  | string      | ❌        | `null`        | Nombre del propietario                                           |
| `marca`  | string      | ❌        | `null`        | Marca del vehículo                                               |
| `modelo` | string      | ❌        | `null`        | Modelo del vehículo                                              |
| `color`  | string      | ❌        | `null`        | Color del vehículo                                               |
| `anio`   | int         | ❌        | `null`        | Año de fabricación                                               |
| `estado` | string      | ❌        | `"autorizado"`| `"autorizado"` · `"sospechoso"` · `"no_registrado"`              |

#### Respuesta exitosa — `201 Created`

```json
{
  "mensaje": "Vehiculo registrado correctamente.",
  "id":      5,
  "placa":   "DEF5678"
}
```

#### Errores posibles

| Código | Descripción                                                   |
|--------|---------------------------------------------------------------|
| `400`  | Estado inválido (no es `"autorizado"`, `"sospechoso"` ni `"no_registrado"`) |
| `409`  | La placa ya existe en la base de datos                        |

---

### `PATCH /vehiculos/{numero}`

Actualiza uno o más campos de un vehículo existente.

| Parámetro | Ubicación | Tipo   | Requerido | Descripción              |
|-----------|-----------|--------|-----------|--------------------------|
| `numero`  | path      | string | ✅        | Número de placa a editar |

#### Cuerpo de la petición — `application/json`

Envía solo los campos que deseas modificar:

```json
{
  "color":  "Rojo",
  "estado": "sospechoso"
}
```

| Campo    | Tipo   | Requerido | Descripción                                                      |
|----------|--------|-----------|------------------------------------------------------------------|
| `dueno`  | string | ❌        | Nuevo nombre del propietario                                     |
| `marca`  | string | ❌        | Nueva marca                                                      |
| `modelo` | string | ❌        | Nuevo modelo                                                     |
| `color`  | string | ❌        | Nuevo color                                                      |
| `anio`   | int    | ❌        | Nuevo año                                                        |
| `estado` | string | ❌        | `"autorizado"` · `"sospechoso"` · `"no_registrado"`              |

#### Respuesta exitosa — `200 OK`

```json
{
  "mensaje": "Vehiculo actualizado correctamente.",
  "placa":   "DEF5678"
}
```

#### Errores posibles

| Código | Descripción                                                   |
|--------|---------------------------------------------------------------|
| `400`  | No se enviaron campos o el estado es inválido                 |
| `404`  | Placa no encontrada en la base de datos                       |

---

### `DELETE /vehiculos/{numero}`

Elimina un vehículo de la base de datos.

| Parámetro | Ubicación | Tipo   | Requerido | Descripción                |
|-----------|-----------|--------|-----------|----------------------------|
| `numero`  | path      | string | ✅        | Número de placa a eliminar |

#### Respuesta exitosa — `200 OK`

```json
{
  "mensaje": "Vehiculo eliminado correctamente.",
  "placa":   "DEF5678"
}
```

#### Errores posibles

| Código | Descripción                      |
|--------|----------------------------------|
| `404`  | Placa no encontrada              |

---

## 4. Cámara en vivo

### `POST /camara/iniciar`

Abre la fuente de video (webcam, cámara IP o archivo) e inicia el loop de detección en segundo plano.

#### Cuerpo de la petición — `application/json` (opcional)

```json
{
  "fuente": "0"
}
```

| Campo    | Tipo   | Requerido | Por defecto | Descripción                                                                          |
|----------|--------|-----------|-------------|--------------------------------------------------------------------------------------|
| `fuente` | string | ❌        | `null` (webcam índice 0) | Índice de webcam (`"0"`, `"1"`, …), ruta a archivo de video, o URL de cámara IP |

#### Respuesta exitosa — `200 OK`

```json
{
  "mensaje": "Camara iniciada.",
  "fuente":  "0"
}
```

#### Errores posibles

| Código | Descripción                                                        |
|--------|--------------------------------------------------------------------|
| `409`  | La cámara ya está activa. Usa `POST /camara/detener` primero       |
| `503`  | Los modelos YOLO/OCR no están cargados (falta `modelo_placas.pt`)  |

---

### `POST /camara/detener`

Detiene el loop de detección de la cámara activa.

**No requiere cuerpo.**

#### Respuesta exitosa — `200 OK`

```json
{
  "mensaje": "Camara detenida."
}
```

#### Errores posibles

| Código | Descripción               |
|--------|---------------------------|
| `409`  | La cámara no está activa  |

---

## 5. Análisis de imágenes y vídeos

Ambos endpoints requieren que los modelos estén cargados (`503` en caso contrario).  
Las detecciones también se emiten por WebSocket (`/ws`) en tiempo real.

---

### `POST /analizar-imagen`

Analiza una imagen estática y devuelve las placas detectadas.

#### Cuerpo de la petición — `multipart/form-data`

| Campo    | Tipo | Requerido | Descripción                                             |
|----------|------|-----------|--------------------------------------------------------------|
| `imagen` | file | ✅        | Archivo de imagen (`.jpg`, `.png`, `.bmp`, etc.)        |

#### Ejemplo con `curl`

```bash
curl -X POST http://localhost:8000/analizar-imagen \
     -F "imagen=@foto_placa.jpg"
```

#### Respuesta exitosa — `200 OK`

```json
{
  "total_detectadas": 1,
  "placas": [
    {
      "placa":     "ABC1234",
      "dueno":     "Juan Pérez González",
      "marca":     "Toyota",
      "modelo":    "Corolla",
      "color":     "Blanco",
      "anio":      2020,
      "estado":    "autorizado",
      "confianza": 0.92,
      "bbox":      [120, 310, 380, 370],
      "timestamp": "2025-06-01T10:35:00.123456"
    }
  ]
}
```

| Campo             | Tipo        | Descripción                                                    |
|-------------------|-------------|----------------------------------------------------------------|
| `total_detectadas`| int         | Número de placas detectadas en la imagen                       |
| `placas`          | array       | Lista de detecciones (ver campos individuales abajo)           |
| `placa`           | string      | Número de placa reconocido                                     |
| `dueno`           | string      | Propietario (o `"Desconocido"`)                                |
| `marca`           | string      | Marca del vehículo                                             |
| `modelo`          | string      | Modelo del vehículo                                            |
| `color`           | string      | Color del vehículo                                             |
| `anio`            | int · null  | Año del vehículo                                               |
| `estado`          | string      | `"autorizado"` · `"sospechoso"` · `"no_registrado"`            |
| `confianza`       | float       | Confianza del detector YOLO (0.0 – 1.0)                        |
| `bbox`            | array[4]    | Bounding box `[x1, y1, x2, y2]` en píxeles                    |
| `timestamp`       | string      | Fecha/hora de la detección (ISO 8601)                          |

#### Errores posibles

| Código | Descripción                                             |
|--------|---------------------------------------------------------|
| `400`  | No se pudo decodificar la imagen                        |
| `503`  | Modelos no cargados                                     |

---

### `POST /analizar-video`

Analiza un archivo de video completo cuadro a cuadro y devuelve las placas únicas detectadas.

> El sistema procesa 1 de cada 4 fotogramas para equilibrar velocidad y precisión.  
> Las placas similares (posibles re-lecturas del mismo vehículo) se consolidan en un único resultado.

#### Cuerpo de la petición — `multipart/form-data`

| Campo   | Tipo | Requerido | Descripción                                        |
|---------|------|-----------|-----------------------------------------------------|
| `video` | file | ✅        | Archivo de video (`.mp4`, `.avi`, `.mov`, etc.)    |

#### Ejemplo con `curl`

```bash
curl -X POST http://localhost:8000/analizar-video \
     -F "video=@grabacion.mp4"
```

#### Respuesta exitosa — `200 OK`

```json
{
  "total_frames":     1200,
  "total_detectadas": 3,
  "placas": [
    {
      "placa":     "ABC1234",
      "dueno":     "Juan Pérez González",
      "marca":     "Toyota",
      "modelo":    "Corolla",
      "color":     "Blanco",
      "anio":      2020,
      "estado":    "autorizado",
      "confianza": 0.95,
      "frame":     48,
      "timestamp": "2025-06-01T10:35:00.123456"
    }
  ]
}
```

| Campo             | Tipo   | Descripción                                              |
|-------------------|--------|----------------------------------------------------------|
| `total_frames`    | int    | Total de fotogramas procesados en el video               |
| `total_detectadas`| int    | Número de placas únicas identificadas                    |
| `placas`          | array  | Mismos campos que en `/analizar-imagen`, más `frame`     |
| `frame`           | int    | Número del fotograma donde se detectó la placa por primera vez |

#### Errores posibles

| Código | Descripción                             |
|--------|-----------------------------------------|
| `400`  | No se pudo abrir el archivo de video    |
| `503`  | Modelos no cargados                     |

---

## 6. WebSocket — detecciones en tiempo real

### `WS /ws`

Conexión WebSocket persistente que recibe cada detección de placa en tiempo real,  
tanto desde la cámara en vivo como desde los endpoints de análisis.

#### Conectar con JavaScript

```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onmessage = (event) => {
  const deteccion = JSON.parse(event.data);
  console.log(deteccion);
};
```

#### Mensaje recibido (JSON)

```json
{
  "tipo":      "deteccion",
  "timestamp": "2025-06-01T10:35:00.123456",
  "placa":     "ABC1234",
  "dueno":     "Juan Pérez González",
  "marca":     "Toyota",
  "modelo":    "Corolla",
  "color":     "Blanco",
  "anio":      2020,
  "estado":    "autorizado",
  "confianza": 0.92
}
```

| Campo       | Tipo        | Descripción                                                 |
|-------------|-------------|-------------------------------------------------------------|
| `tipo`      | string      | Siempre `"deteccion"`                                       |
| `timestamp` | string      | Fecha y hora de la detección (ISO 8601)                     |
| `placa`     | string      | Número de placa reconocido                                  |
| `dueno`     | string      | Propietario del vehículo                                    |
| `marca`     | string      | Marca del vehículo                                          |
| `modelo`    | string      | Modelo del vehículo                                         |
| `color`     | string      | Color del vehículo                                          |
| `anio`      | int · null  | Año del vehículo                                            |
| `estado`    | string      | `"autorizado"` · `"sospechoso"` · `"no_registrado"`         |
| `confianza` | float       | Confianza del detector YOLO (0.0 – 1.0)                     |

> El servidor no procesa mensajes enviados por el cliente; basta con mantener la conexión abierta para seguir recibiendo eventos.

---

## 7. Esquemas Pydantic

### `VehiculoCrear`

```python
class VehiculoCrear(BaseModel):
    placa:  str
    dueno:  Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    color:  Optional[str] = None
    anio:   Optional[int] = None
    estado: Optional[str] = "autorizado"
    # Valores válidos para estado: 'autorizado' | 'sospechoso' | 'no_registrado'
```

### `VehiculoEditar`

```python
class VehiculoEditar(BaseModel):
    dueno:  Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    color:  Optional[str] = None
    anio:   Optional[int] = None
    estado: Optional[str] = None
```

### `CamaraIniciar`

```python
class CamaraIniciar(BaseModel):
    fuente: Optional[str] = None
    # None = webcam (índice 0)
    # "1"  = segunda webcam
    # "rtsp://..." = cámara IP
    # "/ruta/video.mp4" = archivo de video
```

---

## 8. Códigos de estado HTTP comunes

| Código | Significado                                                        |
|--------|--------------------------------------------------------------------|
| `200`  | OK — Petición procesada correctamente                              |
| `201`  | Created — Recurso creado (solo en `POST /vehiculos`)               |
| `400`  | Bad Request — Datos inválidos o formato de archivo incorrecto      |
| `404`  | Not Found — El recurso (placa/vehículo) no existe                  |
| `409`  | Conflict — La placa ya existe o la cámara ya está activa/inactiva  |
| `422`  | Unprocessable Entity — Error de validación Pydantic                |
| `503`  | Service Unavailable — Modelos YOLO/OCR no cargados                 |

---

## Notas generales

- Los números de placa siempre se almacenan y devuelven en **mayúsculas**.
- El sistema usa **PostgreSQL** como base de datos; la tabla `historial` se crea automáticamente al iniciar.  
  La tabla `vehiculos` debe existir previamente con la estructura esperada.
- Las detecciones en tiempo real se propagan a **todos** los clientes WebSocket conectados.
- La autenticación no está implementada en esta versión; se recomienda añadir un middleware de seguridad antes de exponer la API en producción.
