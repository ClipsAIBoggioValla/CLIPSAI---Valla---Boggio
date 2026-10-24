FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Esta imagen ya tiene:
# - Python 3.11
# - CUDA 12.1
# - cuDNN 8
# - PyTorch con soporte GPU

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HUGGINGFACE_HUB_CACHE=/app/whisper_model \
    DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

# Evitar prompt interactivo de tzdata durante apt-get
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl git \
    && rm -rf /var/lib/apt/lists/*

# Verificar que todo esté disponible
RUN python --version \
    && python -c "import torch; print(f'PyTorch {torch.__version__} con CUDA {torch.version.cuda}')" \
    && ffmpeg -version \
    && ffprobe -version

COPY backend_fastapi/requirements.txt ./
RUN pip install -r requirements.txt

# Precargar modelo de Whisper durante el build via snapshot_download
# (evita cold start de 3.3GB en runtime y garantiza que local_files_only funcione)
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('deepdml/faster-whisper-large-v3-turbo-ct2', cache_dir='/app/whisper_model')"

COPY backend_fastapi/app ./app
# Paquete `backend/` (worker RunPod): `app/main.py` importa condicionalmente
# `backend.api.routes.retrim` y `backend.api.routes.stream`.
COPY backend ./backend
# Motor IA (engine.py + dependencias) para el handler de RunPod.
COPY engine.py ./engine.py
COPY main.py ./main.py
COPY whisper_transcriber.py ./whisper_transcriber.py
COPY audio_analyzer.py ./audio_analyzer.py
# Worker RunPod Serverless (script de arranque).
COPY backend_fastapi/runpod_worker.py ./runpod_worker.py
# Alias `backend_fastapi.*` -> `app.*` para que esos routers resuelvan sus imports
# dentro de la imagen. Sin esto la superficie de la API dependía del layout
# (60 rutas en Docker vs 62 desde la raíz del repo).
COPY backend_fastapi/docker-sitecustomize.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

EXPOSE 8000

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

# Cache de HuggingFace con permisos para appuser (modelo ya precargado)
RUN mkdir -p /app/whisper_model /tmp/huggingface_cache \
    && chown -R appuser:appuser /app/whisper_model /tmp/huggingface_cache \
    && chmod -R a+rwX /app/whisper_model /tmp/huggingface_cache

USER appuser

# CMD condicional auto-diagnosticable: RUN_MODE=serverless para RunPod, uvicorn para Render
CMD ["sh", "-c", "echo '[BOOT] RUN_MODE='\"$RUN_MODE\"''; if [ \"$RUN_MODE\" = \"serverless\" ]; then echo '[BOOT] MODO=SERVERLESS (runpod handler)'; exec python runpod_worker.py; else echo '[BOOT] MODO=WEB (uvicorn)'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
