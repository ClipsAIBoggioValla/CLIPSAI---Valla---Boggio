# AGENTS.md — ClipsAI

## Proyecto
ClipsAI — generador de clips verticales con FastAPI (backend_fastapi), React (frontend_react) y worker GPU en RunPod/R2.

## Entorno shell
Windows PowerShell 5.1 — PROHIBIDO usar `&&`; encadenar con `;` o comandos separados.

## Comandos silenciosos
- Backend tests: `pytest -q -x --tb=short`
- Frontend build: `npm --prefix frontend_react run build -- --silent`
- Git estado/diff: `git status -s; git diff --stat`

## Mapa de carpetas
- `backend_fastapi/app/routers/` : endpoints REST (clips, videos, auth)
- `backend_fastapi/app/services/` : r2_service.py, runpod_service.py, publish_service.py
- `frontend_react/` : interfaz web React
- `archive/` : codigo legado (Express/Vue) — PROHIBIDO leer, listar o buscar aqui
- Ignorar siempre: `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `.env*`, archivos de audio/video

## Reglas de codigo y respuesta
- Complejidad ciclomatica por funcion: AST CC <= 4
- Edits minimos: prohibido reescribir archivos completos; sin dependencias nuevas sin aprobacion
- Antes de tocar mas de 1 archivo: responder solo un Plan de maximo 8 viñetas sin editar
- Salida obligatoria: maximo 5 lineas + `git diff --stat`, sin introduccion ni conclusion
