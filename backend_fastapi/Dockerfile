# syntax=docker/dockerfile:1
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HUGGINGFACE_HUB_CACHE=/app/whisper_model

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar curl si no está disponible
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Descargar FFmpeg estático con todos los codecs (incluido libx264)
RUN curl -sSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg-release.tar.xz \
    && tar -xf ffmpeg-release.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-release.tar.xz ffmpeg-*-amd64-static \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Asegurar que /usr/local/bin esté primero en el PATH
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"

# Verificar que ffmpeg tenga libx264
RUN /usr/local/bin/ffmpeg -encoders 2>/dev/null | grep libx264 || (echo "ERROR: libx264 no disponible" && exit 1)

# Verificar versiones y entorno
RUN python --version \
    && python -c "import torch; print(f'PyTorch {torch.__version__} con CUDA {torch.version.cuda}')" \
    && /usr/local/bin/ffmpeg -version \
    && /usr/local/bin/ffprobe -version

# Instalar dependencias de Python
COPY backend_fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# El modelo Whisper se descarga en el primer arranque del worker (evita corrupción en build)

# Copiar código
COPY backend_fastapi/app ./app
COPY backend ./backend
COPY engine.py ./engine.py
COPY main.py ./main.py
COPY whisper_transcriber.py ./whisper_transcriber.py
COPY audio_analyzer.py ./audio_analyzer.py
COPY backend_fastapi/runpod_worker.py ./runpod_worker.py

# Sitecustomize embebido inline: reordena PATH para priorizar FFmpeg del sistema
# (con libx264 en /usr/local/bin) sobre /opt/conda/bin. Python lo importa auto.
COPY <<'PYEOF' /usr/local/lib/python3.11/site-packages/sitecustomize.py
import os

_PRIORITY = [
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
]


def _fix_path() -> None:
    current = os.environ.get("PATH", "")
    partes = [p for p in current.split(os.pathsep) if p and p not in _PRIORITY]
    os.environ["PATH"] = os.pathsep.join(_PRIORITY + partes)


_fix_path()
PYEOF

# Crear directorios y permisos
RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

USER appuser

RUN mkdir -p /tmp/huggingface_cache && chown -R appuser:appuser /tmp/huggingface_cache && chmod -R a+rwX /tmp/huggingface_cache

EXPOSE 8000

CMD ["sh", "-c", "echo '[BOOT] RUN_MODE='\"$RUN_MODE\"''; if [ \"$RUN_MODE\" = \"serverless\" ]; then echo '[BOOT] MODO=SERVERLESS (runpod handler)'; exec python runpod_worker.py; else echo '[BOOT] MODO=WEB (uvicorn)'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
