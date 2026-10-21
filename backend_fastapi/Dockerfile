FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HUGGINGFACE_HUB_CACHE=/tmp/huggingface_cache

WORKDIR /app

# Este paso ya sabemos que funciona y queda en caché (tarda ~60s)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && ffmpeg -version \
    && ffprobe -version \
    && rm -rf /var/lib/apt/lists/*

COPY backend_fastapi/requirements.txt ./
RUN pip install -r requirements.txt

# NOTA: Ya NO está la línea que descargaba el modelo de Whisper durante el build.

COPY backend_fastapi/app ./app
# Paquete `backend/` (worker RunPod): `app/main.py` importa condicionalmente
# `backend.api.routes.retrim` y `backend.api.routes.stream`.
COPY backend ./backend
# Alias `backend_fastapi.*` -> `app.*` para que esos routers resuelvan sus imports
# dentro de la imagen. Sin esto la superficie de la API dependía del layout
# (60 rutas en Docker vs 62 desde la raíz del repo).
COPY backend_fastapi/docker-sitecustomize.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

EXPOSE 8000

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

USER appuser

# Permiso de escritura para que el modelo se descargue en runtime en RunPod
RUN mkdir -p /tmp/huggingface_cache && chown -R appuser:appuser /tmp/huggingface_cache && chmod -R a+rwX /tmp/huggingface_cache

# CMD condicional auto-diagnosticable: RUN_MODE=serverless para RunPod, uvicorn para Render
CMD ["sh", "-c", "echo '[BOOT] RUN_MODE='\"$RUN_MODE\"''; if [ \"$RUN_MODE\" = \"serverless\" ]; then echo '[BOOT] MODO=SERVERLESS (runpod handler)'; exec python -m runpod.serverless.start --handler backend.handler; else echo '[BOOT] MODO=WEB (uvicorn)'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
