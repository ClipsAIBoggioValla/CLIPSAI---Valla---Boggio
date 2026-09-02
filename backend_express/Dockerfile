FROM node:20-slim

ENV NODE_ENV=production \
    PORT=8001

WORKDIR /app

# Dependencias del sistema mínimas (curl para healthcheck + Python y FFmpeg para el motor de IA)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        python3 \
        python3-pip \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Node.js
COPY package*.json ./
RUN npm ci --only=production

# Instalar dependencias de Python requeridas por el motor de subproceso
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

# Copiar el código del backend Express y los scripts del motor Python
COPY src ./src
COPY scripts ./scripts
COPY ../engine.py ../engine_subprocess.py ./

EXPOSE 8001

# Directorio compartido de subidas (volumen clipsai_uploads)
RUN mkdir -p /storage/uploads && chown node:node /storage/uploads

# Usuario no-root (usando el usuario 'node' nativo de la imagen oficial)
RUN chown -R node:node /app
USER node

CMD ["node", "src/app.js"]