FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/runpod-volume/huggingface \
    HUGGINGFACE_HUB_CACHE=/runpod-volume/huggingface/hub \
    TORCH_HOME=/runpod-volume/torch

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar curl + fuentes para libass: el ffmpeg estático renderiza ASS vía
# fontconfig; sin fuentes .ttf instaladas los subtítulos/hook salen invisibles (rc=0).
# fonts-noto-color-emoji: emojis a color en subtítulos (issue #117) — DejaVu no los renderiza.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        fontconfig \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# Verificar que libass tendrá AMBAS fuentes (sin ellas subs/hook/emojis salen invisibles)
RUN fc-list | grep -i "dejavu" \
    && fc-list | grep -i "noto color emoji" \
    || (echo "ERROR: fuentes DejaVu o Noto Color Emoji no instaladas — subs/hook/emojis invisibles" && exit 1)

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

# Instalar dependencias del worker (requirements-worker.txt):
# set completo para el pipeline GPU — librosa/faster-whisper/whisperx (audio+STT),
# mediapipe/opencv/scenedetect (visión #118), yt-dlp (ingesta #119),
# instructor/litellm (LLM estructurado), pysubs2/emoji (subs #117).
# Nota: PyTorch/CUDA vienen de la imagen base; NO usar backend_fastapi/requirements.txt
# aquí (trae fastapi/uvicorn/sqlalchemy que el worker no necesita y fija torch vía index-url).
COPY requirements-worker.txt ./
RUN pip install --no-cache-dir -r requirements-worker.txt

# CUDA 12.8 runtime para CTranslate2/faster-whisper en GPU (base cudnn9).
# Registramos las rutas dinámicamente vía ldconfig (no hardcodear paths ni sonames):
# la imagen base pytorch/pytorch es CONDA, así que los paquetes van a
# /opt/conda/lib/python3.X/site-packages/nvidia/... (no a /usr/local/lib/...).
# cuDNN 9: ctranslate2>=4.5 (el que resuelve faster-whisper>=1.0.3) está compilado
# contra cuDNN 9 — la 8.x de la imagen anterior causaría mismatch de sonames.
RUN pip install --no-cache-dir "nvidia-cudnn-cu12==9.*" "nvidia-cublas-cu12==12.*" && \
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

# Sitecustomize: reordena PATH para priorizar FFmpeg del sistema.
# Ruta resuelta dinámicamente: la base conda usa /opt/conda/lib/python3.X/site-packages
# (el /usr/local/lib/python3.10 fijo de la imagen anterior nunca fue efectivo).
COPY backend_fastapi/docker-sitecustomize.py /tmp/docker-sitecustomize.py
RUN SITE=$(python -c "import site; print(site.getsitepackages()[0])") && \
    cp /tmp/docker-sitecustomize.py "$SITE/sitecustomize.py" && \
    rm /tmp/docker-sitecustomize.py

# Crear directorios de storage
RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

USER appuser

# Directorios de cache sobre el RunPod Network Volume (issue #122): HF_HOME/TORCH_HOME
# apuntan aquí para que el modelo large-v3-turbo persista entre cold starts.
# Se crean con permisos amplios; en runtime RunPod monta el volumen en /runpod-volume
# (el mount reemplaza estos dirs, el chmod es best-effort para dev local).
RUN mkdir -p /runpod-volume/huggingface /runpod-volume/torch \
    /tmp/huggingface_cache \
    && chmod -R a+rwX /runpod-volume /tmp/huggingface_cache 2>/dev/null || true

EXPOSE 8000

CMD ["python", "-u", "runpod_worker.py"]
