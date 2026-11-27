FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/runpod-volume/hf_cache \
    HUGGINGFACE_HUB_CACHE=/runpod-volume/hf_cache/hub \
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

# SFX por mood (issue #116): síntesis propia con lavfi (libres de derechos,
# seed fija = determinístico). El mix aplica volume=0.13 (<= -18 dB) y adelay
# en el ensamble; aquí solo se generan los .wav base en /app/sfx/.
RUN set -eux; mkdir -p /app/sfx; \
    ffmpeg -hide_banner -loglevel error -y \
      -f lavfi -i "anoisesrc=color=brown:seed=117:r=48000:a=0.5" \
      -af "lowpass=f=600,afade=t=in:d=0.55,afade=t=out:st=0.35:d=0.35" -t 0.9 /app/sfx/tension.wav; \
    ffmpeg -hide_banner -loglevel error -y \
      -f lavfi -i "sine=f=55:r=48000:d=0.7" \
      -af "volume=0.8,afade=t=out:st=0.15:d=0.55" -t 0.7 /app/sfx/impact.wav; \
    ffmpeg -hide_banner -loglevel error -y \
      -f lavfi -i "anoisesrc=color=pink:seed=116:r=48000:a=0.6" \
      -af "lowpass=f=1200,afade=t=in:d=0.6,afade=t=out:st=0.3:d=0.3" -t 0.9 /app/sfx/transition.wav; \
    chmod -R a+rX /app/sfx; \
    test -s /app/sfx/tension.wav && test -s /app/sfx/impact.wav && test -s /app/sfx/transition.wav

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
# set completo para el pipeline GPU — librosa/faster-whisper/ctranslate2 (audio+STT),
# mediapipe/opencv/scenedetect (visión #118), yt-dlp (ingesta #119),
# instructor/litellm (LLM estructurado), pysubs2/emoji (subs #117).
# Nota: PyTorch/CUDA vienen de la imagen base; NO usar backend_fastapi/requirements.txt
# aquí (trae fastapi/uvicorn/sqlalchemy que el worker no necesita y fija torch vía index-url).
COPY requirements-worker.txt ./
RUN pip install --no-cache-dir -r requirements-worker.txt "yt-dlp>=2024.11.4"

# CUDA 12.8 runtime para CTranslate2/faster-whisper en GPU (base cudnn9).
# Registramos las rutas dinámicamente vía ldconfig (no hardcodear paths ni sonames):
# la imagen base pytorch/pytorch es CONDA, así que los paquetes van a
# /opt/conda/lib/python3.X/site-packages/nvidia/... (no a /usr/local/lib/...).
# cuDNN 9: ctranslate2>=4.5 (el que resuelve faster-whisper>=1.1.0) está compilado
# contra cuDNN 9 — la 8.x de la imagen anterior causaría mismatch de sonames.
RUN pip install --no-cache-dir "nvidia-cudnn-cu12==9.*" "nvidia-cublas-cu12==12.*" && \
    SITE=$(python -c "import site; print(site.getsitepackages()[0])") && \
    { find "$SITE/nvidia" -maxdepth 2 -type d -name lib 2>/dev/null || true; } > /etc/ld.so.conf.d/nvidia-pip.conf && \
    ldconfig && \
    echo "[worker-docker] nvidia lib dirs registrados en ld.so.conf:" && cat /etc/ld.so.conf.d/nvidia-pip.conf

# Verificación cuDNN/ctranslate2: el SIGABRT (exit code 134) en runtime llega
# cuando ctranslate2 viejo enlaza libcudnn_ops_infer.so.8 (cuDNN 8) sobre esta
# base cuDNN 9. Falla el build si algún .so de ctranslate2 apunta a cuDNN 8 o
# si queda alguna dependencia dinámica "not found".
RUN set -eux; \
    CT2_DIR=$(python -c "import ctranslate2, os; print(os.path.dirname(ctranslate2.__file__))"); \
    SO_LIST=$(find "$CT2_DIR" -name "*.so*" -type f); \
    test -n "$SO_LIST" || { echo "ERROR: ctranslate2 sin binarios .so - instalación rota"; exit 1; }; \
    ldd $SO_LIST > /tmp/ldd_ct2.txt 2>&1; \
    if grep -qE "cudnn[a-z_]*\.so\.8" /tmp/ldd_ct2.txt; then \
      echo "ERROR: ctranslate2 enlaza cuDNN 8 (incompatible con base cuDNN 9) - fijar ctranslate2>=4.5.0"; \
      grep -E "cudnn[a-z_]*\.so\.8" /tmp/ldd_ct2.txt; \
      exit 1; \
    fi; \
    if grep -q "not found" /tmp/ldd_ct2.txt; then \
      echo "ERROR: dependencias dinámicas 'not found' en ctranslate2:"; \
      grep "not found" /tmp/ldd_ct2.txt; \
      exit 1; \
    fi; \
    python -c "import ctranslate2; from importlib.metadata import version; print('[worker-docker] ctranslate2', ctranslate2.__version__, '| faster_whisper', version('faster-whisper'))"

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

# Cache HF preferida en el Network Volume. whisper_transcriber.py valida el mount
# en runtime y reconfigura HF_HOME/HUGGINGFACE_HUB_CACHE a /tmp si no es escribible.
RUN mkdir -p /tmp/cache/huggingface /tmp/cache/torch \
    /tmp/huggingface_cache \
    && chmod -R a+rwX /tmp/cache /tmp/huggingface_cache

EXPOSE 8000

CMD ["python", "-u", "runpod_worker.py"]
