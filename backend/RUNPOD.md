# ClipsAI en RunPod Serverless

## Imagen

Desde la raíz del repositorio:

```bash
docker build -f backend/Dockerfile -t clipsai-runpod .
```

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
