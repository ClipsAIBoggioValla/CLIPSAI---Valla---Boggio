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

# CUDA 12 runtime para CTranslate2/faster-whisper en GPU.
# Registramos las rutas dinámicamente vía ldconfig (no hardcodear paths ni sonames):
# la imagen base pytorch/pytorch es CONDA, así que los paquetes van a
# /opt/conda/lib/python3.10/site-packages/nvidia/... (no a /usr/local/lib/...).
RUN pip install --no-cache-dir "nvidia-cudnn-cu12==8.*" "nvidia-cublas-cu12==12.*" && \
    SITE=$(python -c "import site; print(site.getsitepackages()[0])") && \
    { find "$SITE/nvidia" -maxdepth 2 -type d -name lib 2>/dev/null || true; } > /etc/ld.so.conf.d/nvidia-pip.conf && \
    ldconfig && \
    echo "[worker-docker] nvidia lib dirs registrados en ld.so.conf:" && cat /etc/ld.so.conf.d/nvidia-pip.conf

# Copiar scripts del worker (desde la raíz del repo)
COPY engine.py ./engine.py
COPY main.py ./main.py
COPY whisper_transcriber.py ./whisper_transcriber.py
COPY audio_analyzer.py ./audio_analyzer.py
COPY video_processor.py ./video_processor.py
COPY backend/ ./backend/
COPY backend_fastapi/runpod_worker.py ./runpod_worker.py

# Sitecustomize: reordena PATH para priorizar FFmpeg del sistema
COPY backend_fastapi/docker-sitecustomize.py /usr/local/lib/python3.10/site-packages/sitecustomize.py

# Crear directorios de storage
RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

USER appuser

RUN mkdir -p /tmp/huggingface_cache && chown -R appuser:appuser /tmp/huggingface_cache && chmod -R a+rwX /tmp/huggingface_cache

EXPOSE 8000

CMD ["python", "-u", "runpod_worker.py"]
