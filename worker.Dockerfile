FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/tmp/cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/tmp/cache/huggingface/hub \
    TORCH_HOME=/tmp/cache/torch

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar curl + fuentes para libass: el ffmpeg estático renderiza ASS vía
# fontconfig; sin fuentes .ttf instaladas los subtítulos/hook salen invisibles (rc=0).
# fonts-noto-color-emoji: emojis a color en subtítulos (issue #117) — DejaVu no los renderiza.
# xz-utils: OBLIGATORIO para extraer el .tar.xz de BtbN FFmpeg (no asumir que
# la base conda lo trae; el build viejo dependía del xz de la base 2.1.0).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        fontconfig \
        xz-utils \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# Verificar que libass tendrá AMBAS fuentes (sin ellas subs/hook/emojis salen invisibles)
RUN fc-list | grep -i "dejavu" \
    && fc-list | grep -i "noto color emoji" \
    || (echo "ERROR: fuentes DejaVu o Noto Color Emoji no instaladas — subs/hook/emojis invisibles" && exit 1)

# FFmpeg con NVENC: build BtbN linux64-gpl (--enable-ffnvcodec). El encoder
# h264_nvenc queda registrado en el binario y carga libnvidia-encode.so.1 del
# driver del host en runtime (RunPod lo inyecta) — no hace falta driver en build.
# Release pinneado (reproducible) con fallback a master-latest si el asset cambia.
RUN set -eux; \
    BASE_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"; \
    URL_PINNED="$BASE_URL/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz"; \
    URL_FALLBACK="$BASE_URL/ffmpeg-master-latest-linux64-gpl.tar.xz"; \
    curl -fsSL -o ffmpeg.tar.xz "$URL_PINNED" || curl -fsSL -o ffmpeg.tar.xz "$URL_FALLBACK"; \
    tar -xf ffmpeg.tar.xz; \
    mv ffmpeg-*-gpl*/bin/ffmpeg /usr/local/bin/ffmpeg; \
    mv ffmpeg-*-gpl*/bin/ffprobe /usr/local/bin/ffprobe; \
    rm -rf ffmpeg.tar.xz ffmpeg-*-gpl*/; \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Asegurar que /usr/local/bin esté primero en el PATH
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"

# Checks endurecidos: el binario BtbN debe listar AMBOS encoders (se listan
# sin driver presente; la libnvidia-encode.so.1 se resuelve en runtime en RunPod).
RUN /usr/local/bin/ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "h264_nvenc" \
    || (echo "ERROR: h264_nvenc no disponible en el binario BtbN" && exit 1)
RUN /usr/local/bin/ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "libx264" \
    || (echo "ERROR: libx264 no disponible (fallback CPU roto)" && exit 1)

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

# Caches de modelos: SIEMPRE en /tmp (grabable por appuser). /runpod-volume se
# activa en runtime solo si el Network Volume está montado y escribible — ver
# _directorio_cache_hf() en whisper_transcriber.py (fallback automático).
RUN mkdir -p /tmp/cache/huggingface /tmp/cache/torch \
    /tmp/huggingface_cache \
    && chmod -R a+rwX /tmp/cache /tmp/huggingface_cache

EXPOSE 8000

CMD ["python", "-u", "runpod_worker.py"]
