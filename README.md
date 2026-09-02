# ClipsAI — Plataforma de Generación Automática de Clips Virales

> Procesamiento asíncrono de videos, extracción de transcripciones y generación de clips destacados con metadatos — con **dual-frontend (React + Vue 3)**, **FastAPI**, **PostgreSQL** y **worker asíncrono**.

## 1. Visión General

**ClipsAI** convierte videos largos en clips verticales listos para redes (1080x1920), con subtítulos quemados y hook inicial, a partir de:

```
Video (.mp4/.mov) + Transcripción (.txt)  →  Job asíncrono  →  clips[] con score + preview
```

### Arquitectura

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  React (3000)   │ ──────▶ │                  │ ──────▶ │  PostgreSQL     │
│  Vue 3 (5173/   │         │  FastAPI :8000   │         │  :5432          │
│       3001)     │ ◀────── │  /auth /videos   │ ◀────── │  (volumen       │
└─────────────────┘         │  /jobs /clips    │         │   postgres_data)│
         │                  │  /docs (Swagger) │         └─────────────────┘
         │                  └────────┬─────────┘
         │                           │ BackgroundTasks / Celery (cuando Redis
         │                           ▼  :6379 está configurado)
         │                  ┌──────────────────┐
         └─────────────────▶│  Worker Engine   │
                            │  audio + IA +    │
                            │  FFmpeg          │
                            └──────────────────┘
```

* **Dual-frontend con paridad total**: React (Context + Router + Tailwind) y Vue 3 (Pinia + Router + Tailwind) consumen el mismo contrato HTTP.
* **Backend**: FastAPI + SQLAlchemy + Pydantic, JWT, CORS, `redirect_slashes=False` y handler `OPTIONS` para preflight.
* **Persistencia**: PostgreSQL 15 dockerizada con healthcheck `pg_isready`.
* **Asincronía**: `BackgroundTasks` (por defecto) y extensible a Celery+Redis cuando `.env` define `REDIS_URL`/`CELERY_BROKER`.

---

## 2. Funcionalidades End-to-End

### 2.1 Autenticación & Usuarios
- `POST /auth/registro` — `UsuarioCreate { email, password (≥8), full_name? }` → `201` o `409` si email existe.
- `POST /auth/login` (JSON `{email,password}`) y `POST /auth/login/form` (OAuth2) → `{ access_token, token_type:"bearer" }` (401 en credenciales inválidas, 422 en validación).
- `GET /auth/me` — requiere `Authorization: Bearer <JWT>` (HS256, expiración `JWT_EXPIRE_MINUTES`).
- Frontend: tabs **Login / Registro**, alertas mapeadas 401/409/422 vía `ApiError`, JWT en `localStorage` (`clipsai_token`), rehidratación en `F5` (`/auth/me`), `logout` limpia token.

### 2.2 Ingesta & Subida
- `POST /videos` — `multipart/form-data` `video` (.mp4/.mov/.avi, ≤500MB) + `transcription` (.txt/.srt). Guarda en `UPLOAD_DIR` y persiste `transcript` (primeros 50k chars).
- `GET /videos` — lista del usuario autenticado.
- Frontend (`/upload`, ruta protegida): dos dropzones diferenciados, validación, spinner `Subiendo archivos...` → `Iniciando procesamiento...`.

### 2.3 Sistema de Jobs Asíncrono
```
PENDING → PROCESSING → COMPLETED | FAILED
```
- `POST /videos/{videoId}/jobs` → `202` crea `Job` en `pending` y encola `_run_job` (BackgroundTasks). Valida ownership (`403` si video ajeno, `404` si no existe).
- `GET /jobs/{jobId}` → `{ id, job_id, video_id, status: "COMPLETED", result_metadata, error_message }` (status siempre serializado en `UPPERCASE`).
- `result_metadata.clips` (español, modo simulado sin recorte físico):
  ```ts
  interface Clip { titulo: string; inicio: string; fin: string; score?: number; transcript_preview?: string }
  interface Job { id: string; status: string; result_metadata?: { clips?: Clip[]; video?: string; engine?: string } }
  ```
  Extracción en frontend: `const clips = job?.result_metadata?.clips ?? []` → tarjetas con `titulo`, `Inicio: inicio - Fin: fin`, badge `Score` y preview abreviado + nota "Modo simulado".
- Polling: `useJobPolling` / `useJobPolling` (React/Vue) cada `2000ms` hasta terminal, `clearInterval` en unmount y en `COMPLETED/FAILED`.

### 2.4 Clips CRUD
- `GET /clips?video_id=&status=`, `GET /clips/{id}`, `PATCH /clips/{id} {title?, tags?}`, `DELETE /clips/{id}` (`204`), `GET /clips/{id}/descarga`.

### 2.5 Dual Frontend — Paridad Total

| Capa | React (`frontend_react`) | Vue 3 (`frontend_vue`) |
|------|--------------------------|------------------------|
| Lenguaje | TypeScript 5.5, `tsc -b` strict | TypeScript 5.5, `vue-tsc --noEmit` |
| Estado Auth | `Context/AuthContext.tsx` + `localStorage` | `Pinia` store `useAuthStore` + `localStorage` |
| Router | `react-router-dom` 6, `ProtectedRoute` | `vue-router` 4, `beforeEach` guard |
| HTTP | `fetch` (`src/lib/apiClient.ts`, `BASE_URL = VITE_API_URL \|\| :8000`, `Bearer` auto, `parseError` 400/401/409/422) | `axios` (`src/api/client.ts`, `baseURL`, interceptors idem) |
| Servicios | `src/services/api.ts` → `authService / videoService / jobService / clipService` con normalización `title/filename` y `status.toUpperCase()` | `src/api/services.ts` idem |
| UI | Tailwind 3.4 oscuro, `AuthPage / UploadPage / JobStatusPage` | Tailwind 3.4 oscuro, `AuthView / UploadView / JobStatusView` (Composition API `<script setup>`) |
| Polling | `src/hooks/useJobPolling.ts` 2000ms | `src/composables/useJobPolling.ts` 2000ms |
| Build | `vite` 5.3 | `vite` 5.3 + `@vitejs/plugin-vue` 5 |

---

## 3. Requisitos Previos

| Herramienta | Versión | Notas |
|-------------|---------|-------|
| Node.js | **v18+** (probado en 18/20/22/24) | `node --version` |
| npm | 9+ | incluido con Node |
| Docker + Docker Compose | v20+ / v2+ | `docker compose version` |
| Python | 3.10+ | solo si corres el motor/FFmpeg fuera de Docker |
| FFmpeg | último | requerido por `engine.py` para recorte real |

---

## 4. Guía Completa de Comandos y Puesta en Marcha

### 4.0 Variables de entorno

```bash
cp .env.example .env
# Edita .env — mínimo requerido:
# POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT=5432
# JWT_SECRET=<openssl rand -hex 32>, JWT_ALGORITHM=HS256, JWT_EXPIRE_MINUTES=60
# BACKEND_FASTAPI_PORT=8000
# DATABASE_URL opcional (por defecto usa db:5432 dentro de compose)
```

Frontends usan `VITE_API_URL`:

```bash
# frontend_react/.env y frontend_vue/.env
VITE_API_URL=http://localhost:8000
```

### A) Backend & Servicios (Docker Compose)

```bash
# Levanta PostgreSQL :5432 + FastAPI :8000 (y Redis/Celery si los añades al compose)
docker compose up -d
docker compose up -d --build backend_fastapi  # tras editar app/main.py

# Verificación
curl http://localhost:8000/health          # {"status":"ok"}
curl http://localhost:8000/docs            # Swagger UI
curl -i -X OPTIONS http://localhost:8000/auth/registro \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST"  # 200 con CORS

# Logs
docker compose logs -f backend_fastapi   # o: docker compose logs -f backend
docker compose logs -f worker            # si usas Celery worker
docker compose logs -f db

# Reinicio tras cambios de CORS / redirect_slashes
docker compose restart backend_fastapi

# Parada
docker compose down          # mantiene volumen postgres_data
docker compose down -v       # borra DB (¡cuidado!)
```

> CORS está configurado en `backend_fastapi/app/main.py`:
> ```py
> app = FastAPI(redirect_slashes=False)
> app.add_middleware(CORSMiddleware,
>   allow_origins=["http://localhost:3000","http://127.0.0.1:3000",
>                  "http://localhost:3001","http://127.0.0.1:3001",
>                  "http://localhost:5173","http://127.0.0.1:5173"],
>   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
> # + middleware OPTIONS que responde 200 a preflights
> ```
> Si usas puerto distinto, añádelo a `allow_origins` o usa `["*"]` en desarrollo (no compatible con `allow_credentials=True` en prod).

### B) Frontend React (`frontend_react`)

```bash
cd frontend_react
npm install

# Desarrollo — http://localhost:3000 (proxy /api → :8000 si VITE_API_URL vacío)
npm run dev

# Validación estática (TypeScript strict, noUnusedLocals/Parameters)
npm run typecheck        # tsc --noEmit
# o
npx tsc --noEmit
npx tsc -b

# Build producción
npm run build            # tsc -b && vite build  → dist/
npm run preview -- --port 3000   # sirve dist/ en :3000
```

### C) Frontend Vue 3 (`frontend_vue`)

```bash
cd frontend_vue
npm install

# Validación estática Vue + TS
npx vue-tsc --noEmit
npm run typecheck        # alias de lo anterior

# Desarrollo — http://localhost:5173 (Vite por defecto)
npm run dev              # vite --port 3000 si quieres alinear con React, pero por defecto :5173
# Para correr lado a lado con React:
npm run preview -- --port 3001   # o npm run dev -- --port 3001

# Build producción
npm run build            # vue-tsc --noEmit && vite build  → dist/
npm run preview -- --port 3001
```

> Puertos recomendados lado a lado: React `:3000`, Vue `:3001` (o `:5173`), Backend `:8000`. Todos están en `allow_origins`.

---

## 5. Guía de Testing y Validación Lado a Lado

Ejecuta **tres** procesos simultáneos:

```bash
# Terminal 1 — infra
docker compose up -d && docker compose logs -f backend_fastapi

# Terminal 2 — React
cd frontend_react && npm run dev   # :3000

# Terminal 3 — Vue
cd frontend_vue && npm run dev -- --port 3001  # :3001 (o :5173)
# Alternativa con builds: npm run preview -- --port 3000/3001
```

### Flujo de prueba (repetir en ambos frontends contra el mismo backend :8000)

1. **Registro** — `http://localhost:3000/auth` y `http://localhost:3001/auth` → *Registrarse* → `test_ui@clipsai.com` / `Test12345!` → `201`. Reintentar mismo email → alerta `409 El email ya está registrado`.
2. **Login** — *Iniciar Sesión* con credenciales → JWT en `Application > LocalStorage > clipsai_token`. Login con password errónea → alerta `401 Credenciales inválidas`.
3. **Persistencia** — `F5` en `/upload` → sigue autenticado (AuthStore/Context revalida con `GET /auth/me`, `isLoading` muestra spinner).
4. **Subida** — `/upload` → seleccionar `video.mp4` + `transcript.txt` → botón `Subir y procesar` muestra `Subiendo archivos...` → `Iniciando procesamiento...` (barra `animate-pulse`). Network: `POST /videos 201` → `POST /videos/{id}/jobs 202`.
5. **Tracking** — redirección automática a `/jobs/{jobId}` → polling `GET /jobs/{id}` cada 2s (ver en Network, sin `F5`):
   - `PENDING` → badge ámbar *En cola...*
   - `PROCESSING` → spinner sky *Procesando video y generando clips...*
   - `COMPLETED` → badge verde *¡Procesamiento Completado!* + `3 clips generados · motor: ...` + tarjetas informativas (modo simulado):
     ```
     [titulo]                          [Score 0.92]
     Inicio: 00:01:30 - Fin: 00:02:00
     "transcript_preview truncado..."
     Modo simulado — sin archivo recortado
     ```
   - `FAILED` → alerta roja con `error_message`.
6. **Logout** → `useAuthStore.logout()` / `AuthContext.logout()` limpia `localStorage` → `Navigate /auth`.

### Validación rápida sin UI

```bash
# Registro + login + me
curl -X POST http://localhost:8000/auth/registro -H "Content-Type: application/json" \
  -d '{"email":"test_ui@clipsai.com","password":"Test12345!"}'
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"test_ui@clipsai.com","password":"Test12345!"}' | jq -r .access_token)
curl http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

---

## 6. Estándares de Git y Estructura del Repositorio

### Jerarquía

```
.
├── backend_fastapi/          # FastAPI + SQLAlchemy + Pydantic
│   ├── app/
│   │   ├── main.py           # FastAPI + CORSMiddleware (primero) + OPTIONS handler + redirect_slashes=False
│   │   ├── routers/          # auth, videos, jobs, clips (APIRouter sin restricciones OPTIONS)
│   │   ├── schemas/          # Usuario, Token, Video, Job (status UPPER), Clip
│   │   ├── models.py         # Usuario, Video, Job, Clip
│   │   └── services/engine.py# motor clipsai
│   ├── Dockerfile
│   └── requirements.txt
├── frontend_react/           # React 18 + TS + Router + Context + Tailwind + Vite
│   ├── src/
│   │   ├── types/api.ts      # User*, AuthToken, Video*, Job {result_metadata.clips}, ApiError
│   │   ├── lib/apiClient.ts  # fetch, BASE_URL=VITE_API_URL||:8000, Bearer, parseError 401/409/422
│   │   ├── services/api.ts   # authService / videoService / jobService (+normalize)
│   │   ├── context/AuthContext.tsx
│   │   ├── hooks/useJobPolling.ts (2000ms)
│   │   ├── pages/AuthPage, UploadPage, JobStatusPage
│   │   └── components/ProtectedRoute
│   ├── index.html            # entry Vite en raíz
│   ├── vite.config.ts        # alias @, proxy /api
│   └── .env.example
├── frontend_vue/             # Vue 3 + TS + Pinia + Router + Axios + Tailwind + Vite
│   ├── src/
│   │   ├── types/api.ts      # paridad con React
│   │   ├── api/client.ts     # axios baseURL + interceptors
│   │   ├── api/services.ts
│   │   ├── stores/auth.ts    # Pinia useAuthStore (init/login/register/logout)
│   │   ├── composables/useJobPolling.ts
│   │   ├── router/index.ts
│   │   └── views/AuthView, UploadView, JobStatusView.vue (<script setup>)
│   ├── index.html
│   └── .env.example
├── init-scripts/             # DDL inicial PostgreSQL
├── docker-compose.yml        # db :5432 + backend_fastapi :8000
├── .env/.env.example
└── PROYECTO.md / ISSUES.md
```

### `.gitignore` — exclusión garantizada

```gitignore
# Raíz .gitignore
node_modules/
.env
frontend_react/.env
__pycache__/ / *.pyc
clips/ clips_editados/ gaming_procesado/
audio.mp3 / audio.json / ...

# frontend_react/.gitignore  y  frontend_vue/.gitignore
node_modules/
dist/
.dist
.env
.env.local
.DS_Store
```

* `node_modules/` nunca se commitea (eliminado del índice con `git rm -r --cached`).
* `.env` nunca se commitea (solo `.env.example`).
* `dist/` / `.dist` generados por `vite build` ignorados.
* Verificación: `git ls-files | grep node_modules` → vacío; `git check-ignore -v frontend_react/node_modules` → `frontend_react/.gitignore:1:node_modules/`.

### Ramas y commits

* Rama activa: `feat/frontend-flujo-entrada` (ver `git branch --show-current`).
* Convención: `feat:`, `fix:`, `chore:` (ej. `chore: eliminar node_modules del seguimiento`).
* Tras editar CORS/backend: `docker compose up -d --build backend_fastapi` para aplicar.

---

## Swagger

Una vez levantado el backend: **http://localhost:8000/docs** (OpenAPI interactivo) y **http://localhost:8000/redoc**.

## Licencia

Uso interno / académico — sin licencia pública definida. No subir secretos a Git.
