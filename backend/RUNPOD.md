# ClipsAI en RunPod Serverless

## Imagen

Desde la raíz del repositorio:

```bash
docker build -f worker.Dockerfile -t clipsai-worker .
```

Usa `worker.Dockerfile` para el endpoint GPU descrito aquí; `backend/Dockerfile`
es una imagen legacy distinta y no participa en este cache persistente.

Configura la imagen creada en un endpoint RunPod Serverless con GPU y define
`ANTHROPIC_API_KEY` como variable/secret del endpoint. El worker también recibe
videos de hasta 500 MB y transcripciones de hasta 10 MB.

## Entrada del handler

`backend/handler.py` procesa el motor activo `run_clip_engine` y acepta:

```json
{
  "input": {
    "video_url": "https://storage.example/video.mp4",
    "transcription_url": "https://storage.example/transcript.txt",
    "video_id": "opcional"
  }
}
```

La transcripción es opcional. En su lugar se puede enviar `transcription_text`.
Las URLs deben ser HTTPS/HTTP públicas o URLs prefirmadas accesibles desde RunPod;
el worker no puede leer rutas locales del contenedor FastAPI. El resultado JSON
contiene títulos, rangos, score y metadatos de los candidatos. Los archivos de
video generados deben persistirse en almacenamiento externo si también se
necesitan fuera de la ejecución efímera del worker.

## Cliente desde FastAPI

Define `RUNPOD_API_KEY` y `RUNPOD_ENDPOINT_ID` en el entorno de FastAPI y llama:

```python
from backend_fastapi.app.services.runpod_service import process_video_via_runpod

result = process_video_via_runpod(
    video_url="https://storage.example/video.mp4",
    transcription_url="https://storage.example/transcript.txt",
)
```

El cliente usa `POST /runsync`; si RunPod devuelve un job en progreso, consulta
`/status/{job_id}` hasta completarlo. Los timeouts se pueden ajustar con
`RUNPOD_REQUEST_TIMEOUT_SECONDS`, `RUNPOD_TIMEOUT_SECONDS` y
`RUNPOD_POLL_INTERVAL_SECONDS`. `RUNPOD_API_BASE_URL` permite sustituir la base
de API en entornos de prueba.

## Network Volume para Whisper (#122)

En el endpoint Serverless, adjunta un **Network Volume** al mount path
`/runpod-volume`. La imagen ejecuta como `appuser` (no root): el directorio
`/runpod-volume/hf_cache` debe existir o poder crearse por ese UID y tener
permiso de escritura. No montes el volumen como solo lectura. Conserva los
archivos del modelo entre workers y despliegues; no incluyas el modelo dentro de
la imagen Docker.

Rutas en runtime:

| Variable/ruta | Uso |
|---|---|
| `HF_HOME=/runpod-volume/hf_cache` | Raíz persistente de Hugging Face |
| `HUGGINGFACE_HUB_CACHE=/runpod-volume/hf_cache/hub` | Snapshots/repositorios descargados |
| `download_root` de faster-whisper | La misma ruta `.../hub` |
| Fallback | `/tmp/cache/huggingface` y `/tmp/cache/huggingface/hub` |

`whisper_transcriber.py` comprueba que el mount esté disponible y escribible
antes de elegirlo, crea `hf_cache/hub` cuando el mount permite escritura y
actualiza las variables HF para el proceso. Sin mount, o ante permisos
insuficientes, usa `/tmp`; ese fallback es efímero y no reduce cold start.
`WHISPER_MODEL_PATH` sigue aceptando un modelo local explícito. En un cache hit
se resuelve el snapshot local y faster-whisper usa `local_files_only=True`;
solo un miss permite descargar el repo.

### Precarga y verificación operativa

1. Adjunta el volumen al endpoint y ejecuta una primera transcripción Whisper
   para poblarlo. Esta primera descarga requiere acceso a Hugging Face; no la
   cuentes como prueba de egreso cero.
2. Repite una invocación en un worker nuevo/warm con el mismo volumen. Los logs
   `[Whisper] Cache hit en disco` y `Modelo hit en disco` confirman lectura del
   snapshot; `hit en memoria` indica reutilización de la instancia en el mismo
   proceso. `carga=...s` mide la construcción/carga del modelo.
3. Mide el tiempo desde el inicio del worker hasta el log de modelo listo en
   RunPod. El objetivo de cold start con cache existente es **<4 s**; guarda
   ese intervalo, GPU/worker y timestamp al verificarlo. Pytest no puede
   garantizar el umbral: depende del hardware, montaje y estado del worker.
4. Confirma que no aparezca `Cache miss` ni descarga del modelo y revisa
   métricas de red/egress del pod o una captura de red durante la segunda
   invocación: con el snapshot completo, `local_files_only=True` debe evitar
   egress HF. Si aparece miss, revisa permisos, mount path y modelo precargado.

El handler no registra URLs prefirmadas del watermark ni sus query strings.
Para watermark en RunPod, `render_config.watermark_path` debe ser una URL
HTTP(S) accesible desde el pod; los paths locales del backend no se comparten.
La descarga tiene SSRF guard y límite de 5 MB. Si no hay plan/Brand Kit (#130)
o no llega una fuente aplicable, el default es `watermark=false` y no se añade
ninguna marca.

## Lifecycle 24h en el bucket R2 (Issue #114)

Para evitar acumulación indefinida de videos subidos directamente al bucket,
aplica una regla de lifecycle que expira objetos bajo el prefijo `uploads/`
tras 1 día:

### Variables de entorno necesarias

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `BUCKET_NAME` | Nombre del bucket R2 | `clipsai-videos` |
| `AWS_ACCESS_KEY_ID` | Credencial de acceso R2 | — |
| `AWS_SECRET_ACCESS_KEY` | Secreto de acceso R2 | — |
| `AWS_ENDPOINT_URL` | Endpoint S3 de Cloudflare R2 | `https://<account>.r2.cloudflarestorage.com` |
| `AWS_REGION` | Región (R2 acepta `auto`) | `auto` |
| `R2_PUBLIC_URL` | Dominio público del bucket | `https://videos.clipsai.xyz` |

### Aplicar la regla de lifecycle

Desde la raíz del repositorio, con el entorno de `backend_fastapi` activado:

```bash
# Opción 1: entrypoint CLI del servicio R2
python -m backend_fastapi.app.services.r2_service --apply-lifecycle --bucket clipsai-videos --prefix uploads/

# Opción 2: AWS CLI (Cloudflare R2 es compatible con S3)
aws s3api put-bucket-lifecycle-configuration \
  --bucket clipsai-videos \
  --configuration '{"Rules":[{"ID":"r2-uploads-24h","Status":"Enabled","Filter":{"Prefix":"uploads/"},"Expiration":{"Days":1}}]}'
```

La regla es idempotente: ejecutarla varias veces sobrescribe la misma regla
sin crear duplicados. Los inputs temporales de RunPod (`runpod-inputs/{uuid}`)
se borran por job en `runpod_service.py` (`_borrar_objeto_s3` en el `finally`),
por lo que la regla de bucket cubre específicamente `uploads/` (subidas
directas desde el navegador que no se consumen).
