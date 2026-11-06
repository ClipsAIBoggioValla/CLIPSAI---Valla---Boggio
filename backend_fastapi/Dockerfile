FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HUGGINGFACE_HUB_CACHE=/tmp/huggingface_cache

WORKDIR /app

# Dependencias del sistema: ffmpeg para reframe/cortes/subtítulos ASS + curl healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && ffmpeg -version \
    && ffprobe -version \
    && rm -rf /var/lib/apt/lists/*

# Verificar que ffmpeg tenga libx264 (necesario para editor.py y ffmpeg_service.py)
RUN ffmpeg -encoders 2>/dev/null | grep libx264 || (echo "ERROR: libx264 no disponible" && exit 1)

COPY requirements.txt ./
RUN pip install -r requirements.txt

# El modelo Whisper se descarga en el primer arranque si no está cacheado

COPY app ./app

# Storage persistente para clips renderizados
RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

EXPOSE 8000

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage
USER appuser

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
