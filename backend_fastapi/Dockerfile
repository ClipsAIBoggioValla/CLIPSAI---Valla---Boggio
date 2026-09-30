FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HUGGINGFACE_HUB_CACHE=/tmp/huggingface_cache

WORKDIR /app

# Dependencias del sistema: ffmpeg/ffprobe para render ASS/Hook + curl healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && ffmpeg -version \
    && ffprobe -version \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('deepdml/faster-whisper-large-v3-turbo-ct2', device='cpu', compute_type='int8')"
RUN chmod -R a+rX /tmp/huggingface_cache

COPY app ./app

# Storage persistente para clips renderizados (ASS + Hook) — Issue #29
RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

EXPOSE 8000

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
