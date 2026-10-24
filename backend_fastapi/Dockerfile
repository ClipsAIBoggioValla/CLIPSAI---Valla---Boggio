FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HUGGINGFACE_HUB_CACHE=/app/whisper_model

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar dependencias del sistema + CUDA runtime mínimo
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        git \
        wget \
    # Descargar e instalar CUDA runtime 12.1 (solo bibliotecas necesarias)
    && wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1.deb \
    && rm cuda-keyring_1.1-1.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        cuda-libraries-12-1 \
        cuda-nvtx-12-1 \
    && rm -rf /var/lib/apt/lists/*

# Verificar
RUN python --version \
    && ffmpeg -version \
    && ffprobe -version \
    && ldconfig -p | grep cuda || echo "CUDA libs instalados"

# Instalar dependencias de Python (torch con CUDA)
COPY backend_fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Descargar modelo Whisper
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('deepdml/faster-whisper-large-v3-turbo-ct2', cache_dir='/app/whisper_model')"

COPY backend_fastapi/app ./app
COPY backend ./backend
COPY engine.py ./engine.py
COPY main.py ./main.py
COPY whisper_transcriber.py ./whisper_transcriber.py
COPY audio_analyzer.py ./audio_analyzer.py
COPY backend_fastapi/runpod_worker.py ./runpod_worker.py
COPY backend_fastapi/docker-sitecustomize.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

USER appuser

RUN mkdir -p /tmp/huggingface_cache && chown -R appuser:appuser /tmp/huggingface_cache && chmod -R a+rwX /tmp/huggingface_cache

EXPOSE 8000

CMD ["sh", "-c", "echo '[BOOT] RUN_MODE='\"$RUN_MODE\"''; if [ \"$RUN_MODE\" = \"serverless\" ]; then echo '[BOOT] MODO=SERVERLESS (runpod handler)'; exec python runpod_worker.py; else echo '[BOOT] MODO=WEB (uvicorn)'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
