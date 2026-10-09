FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HF_HUB_DOWNLOAD_TIMEOUT=60 \
    HF_HUB_ETAG_TIMEOUT=60 \
    HUGGINGFACE_HUB_CACHE=/tmp/huggingface_cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && ffmpeg -version \
    && ffprobe -version \
    && rm -rf /var/lib/apt/lists/*

# Install the same application dependencies as FastAPI plus the RunPod SDK.
COPY backend/requirements.txt backend/requirements.txt
COPY backend_fastapi/requirements.txt backend_fastapi/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Cache the Whisper model in the image; inference uses the available CUDA GPU.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('deepdml/faster-whisper-large-v3-turbo-ct2', device='cpu', compute_type='int8')" \
    && chmod -R a+rX /tmp/huggingface_cache

# CUDA 12 runtime para CTranslate2/faster-whisper en GPU: cuDNN 8 aporta
# libcudnn_ops_infer.so.8 y cuBLAS/cuda-runtime los sonames CUDA 12 (la base trae CUDA 11.8).
RUN pip install --no-cache-dir "nvidia-cudnn-cu12==8.*" "nvidia-cublas-cu12==12.*" \
    && ls /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/libcudnn_ops_infer.so.8

ENV LD_LIBRARY_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH}"

# Copy only runtime code and the marker used to locate the repository root.
COPY backend/ backend/
COPY backend_fastapi/app/ backend_fastapi/app/
COPY SISTEMA.md docker-compose.yml ./

CMD ["python", "-u", "backend/handler.py"]
