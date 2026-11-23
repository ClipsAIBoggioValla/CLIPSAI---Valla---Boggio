# Contexto de build: RAÍZ del repo (Issue #110) — frontend_common debe estar
# disponible como carpeta hermana para la dependencia file:../frontend_common.
#   docker build -f frontend_react/Dockerfile -t clipsai-frontend .
FROM node:20-alpine AS builder
WORKDIR /app
# /app/../frontend_common => /frontend_common (resuelve el file: del package.json)
COPY frontend_common /frontend_common
COPY frontend_react/package.json frontend_react/package-lock.json ./
RUN npm ci
COPY frontend_react/vite.config.ts frontend_react/tsconfig.json frontend_react/index.html ./
COPY frontend_react/tailwind.config.js frontend_react/postcss.config.js ./
COPY frontend_react/src ./src
RUN npx vite build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
