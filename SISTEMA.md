# CLIPSAI — Documentación Integral del Sistema (2026)

> **Propósito:** describir de arriba a abajo qué hace el sistema hoy, con qué lo hace y qué falta, para decidir nuevas issues. Cubre infraestructura, modelo de datos, motor IA, backends duales (FastAPI/Express), frontends duales (React/Vue), flujos E2E, seguridad, despliegue y deuda.

---

## 1. Visión y Alcance

Convertir videos largos (podcast/stream/entrevista, gaming enfocado a un solo formato 1080x1920) en clips verticales 9:16 listos para TikTok/Reels/Shorts con scoring viral IA, subtítulos quemados (pipeline ASS/FFmpeg existente pero no integrado en `jobs`), hook teaser opcional y **publicación automática** (Issue #12).

**Flujo canónico:**
```
Video (.mp4/.mov/.avi) + Transcripción (.txt/.srt) 
→ POST /videos (multipart) → POST /videos/{id}/jobs (202) 
→ Job pending→processing→completed (+ clips) 
→ GET /clips (biblioteca) → PATCH/DELETE/descarga 
→ POST /clips/{id}/publicar (202 → PUBLISHING → PUBLISHED) → badge verde + URL
→ /stats, /metrics, /export (csv/json), /docs
```

Fuera de alcance: live, multi-cámara, timeline manual, traducción multi-idioma, móvil nativo, distribuido multi-host.

---

## 2. Arquitectura de Despliegue

```
              ┌─────────────┐
 React :3000 ─┤             ├──┐
              │ FastAPI :8000│  ▼
 Vue :5173 ───┤ /auth /videos│ PostgreSQL :5432
              │ /jobs /clips │  ▲  (volume postgres_data, healthcheck pg_isready)
              │ /publish/exp │  │
              │ /docs        │  │
              └──────┬───────┘  │
                     │ BackgroundTasks
                     ▼         │
              ┌─────────────┐ │
              │ Motor IA     │─┘
              │ audio+whisp │   engine.py + main.py (librosa, faster-whisper, Claude/OpenRouter)
              │ +LLM+FFmpeg │   fallback determinístico si LLM falla → COMPLETED
              └─────────────┘
 Express :3001 ──► misma DB + mismo JWT (HS256, 60min) ──► spawnSync python engine.py --json
```

- **Red:** `clipsai-net` bridge
- **Volumen:** `clipsai_postgres_data` persiste `down`/`up`
- **Healthcheck:** `db pg_isready`, `fastapi curl /health`, `express node fetch /health`
- **CORS:** `3000,3001,5173` + middleware OPTIONS manual (FastAPI)
- **Async:** `BackgroundTasks` (FastAPI) / `setImmediate` (Express). Migrable a Celery/Redis si `REDIS_URL`.

> Estado `docker-compose.yml` actual: `db + backend_fastapi + backend_express`. Faltan `frontend_react`/`frontend_vue` como servicios (ver §13).

---

## 3. Stack Tecnológico

| Capa | Tech | Notas |
|------|------|-------|
| Orquestación | Docker + Compose v2 | `postgres:15-alpine`, healthchecks |
| DB | PostgreSQL 15 + `uuid-ossp` | triggers `updated_at`, CHECK constraints `lower()` case-insensitive |
| Backend #1 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 sync + Pydantic 2 + python-jose + bcrypt + uvicorn | `redirect_slashes=False`, lifespan migrations |
| Backend #2 | Node 20 + Express 4.19 + pg 8.11 + jsonwebtoken + bcryptjs + multer + tsx + TS 5.5 | `type:module`, pool normaliza `postgresql+psycopg2://` |
| Frontend #1 | React 18.3 + TS 5.5 + react-router 6 + Context + Tailwind 3.4 + Vite 5.3 + recharts | `fetch` apiClient, `useJobPolling` 2s |
| Frontend #2 | Vue 3.4 + TS 5.5 + vue-router 4 + Pinia 2 + Axios + Tailwind 3.4 + Vite 5.3 | interceptors 401→/login, composable polling |
| Motor IA | Python + librosa + faster-whisper large-v3-turbo + scikit-learn KMeans + Anthropic Claude / OpenAI / OpenRouter / DeepSeek + FFmpeg + requests | pipeline `extraer_audio→analizar→formatear→enriquecer→LLM→validar→cortar` |
| Estilos | Tailwind + `spark.css` Cyber-Tech Dark | `#0B0F17` bg, `#080C14` sidebar, `#121824` card, `#B4F105` lime glow |
| Otros | `requests`, `python-dotenv`, `anthropic 0.64` | `PUBLISH_WEBHOOK_URL` para publish |

---

## 4. Modelo de Datos (PostgreSQL + ORM)

### 4.1 Esquema relacional

```
usuarios 1──N videos 1──N jobs 1──N clips
```

| Tabla | Columnas clave | Constraints / Índices |
|-------|---------------|----------------------|
| **usuarios** | `id UUID PK`, `email UNIQUE`, `hashed_password`, `full_name`, `avatar_url`, `theme_preference`, `created_at/updated_at` | trigger `set_updated_at()`, índice email |
| **videos** | `id UUID PK`, `usuario_id FK CASCADE`, `original_filename`, `file_path`, `transcription_filepath`, `transcript TEXT (50k)`, `duration_seconds`, `created_at` | `idx_videos_usuario_id` |
| **jobs** | `id UUID PK`, `video_id FK CASCADE`, `status pending/processing/completed/failed` (via `lower()` CHECK), `result_metadata JSONB`, `error_message` | `idx_jobs_video_id`, `chk_jobs_status` |
| **clips** | `id UUID PK`, `job_id FK CASCADE`, `video_id`, `title`, `file_path`, `start_time/end_time FLOAT` `chk_time_range`, `score`, `tags JSONB`, `status` (`ready/PUBLISHING/PUBLISHED/FAILED`), `publication_status` (`PUBLISHING/PUBLISHED/FAILED/DRAFT` via `lower()` CHECK), `published_platform`, `social_post_id/url`, `published_at`, `social_network` (`lower()` CHECK), `error_log` | `idx_clips_job_id` |

### 4.2 Migraciones runtime (`backend_fastapi/app/main.py:lifespan`)

- `Base.metadata.create_all` + 12 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (videos transcription, jobs result_metadata, clips published_* etc.)
- Recrea `chk_jobs_status` como `lower(status) IN (...)` y `chk_clips_publication_status` como `lower(publication_status) IN ('draft','scheduled','published','failed','not_published','publishing')` + `chk_clips_social_network` con `lower()` para aceptar `PUBLISHING` mayúsculas sin violación.
- Idempotente; Express hace `ensurePublishColumns()` fire-and-forget.

### 4.3 Entidades Pydantic / ORM

- `Clip.status = "PUBLISHING"|"PUBLISHED"|"FAILED"|"ready"` (computado), `publication_status` espejo mayúsculas.
- `ClipResponse` expone `published_platform/social_post_id/url/published_at`.

---

## 5. Motor IA (Python)

### 5.1 Pipeline (`main.py` 964L + `engine.py` 378L wrapper + `engine_subprocess.py`)

1. **Validación + FFmpeg check** + `tempfile.mkdtemp(prefix=clipsai_)`
2. **Extraer audio** `ffmpeg -y -i video -q:a 0 -map a audio.mp3`
3. **Analizar audio** `audio_analyzer.analizar_audio` (RMS 2048/512 → eventos grito/silencio/cambio_brusco → momentos intensos ventana 5 → onset KMeans 10 → `audio.json/momentos_virales.json` top50)
4. **Formatear transcripción** regex `HH:MM:SS - Texto`
5. **Preparar para IA** comprime a 150 segmentos
6. **Enriquecer** correlación audio↔transcripción <30s
7. **Prompt + LLM** `construir_prompt` experto viral rioplatense, 6 criterios pesados, reglas 30-90s óptimo 45-70s, output JSON `[{inicio,fin,duracion,score,criterio_principal,titulo_sugerido,hook_texto,primer_segundo,motivo}]`
   - `hook_service.py` + `main.py` soportan **ANTHROPIC_API_KEY** (x-api-key/anthropic-version) **prioritario**, fallback `OPENAI_API_KEY` → `OPENROUTER_API_KEY` → `DEEPSEEK_API_KEY` (OpenAI-compat). `logger.exception` + reintentos `2*intento` sleep + `429 Retry-After`.
   - Si LLM falla → `_mock_hooks` / `_fallback_result` determinístico (2 clips `00:00:10-00:00:45`, `00:01:00-00:01:35`) para no dejar `FAILED`.
8. **Validar clips** filtra 30-90s, score≥5, top10, sort score desc
9. **Cortar** `ffmpeg -ss inicio -i video -t duracion -c:v libx264 ultrafast crf18 -c:a aac`
10. **Wrapper** `engine.py:procesar_video() → ProcesamientoResultado {exito, clips: ClipInfo[], carpeta_salida, error_tipo}` con manejo granular `ValidacionError|DependenciaError|AudioError|IAError|Timeout|SinClipsValidos`.

### 5.2 Servicios adicionales

- `whisper_service.py` 177L: `faster-whisper large-v3-turbo`, `cuda/float16` else `cpu/int8`, `vad_filter`, `beam 5`.
- `ass_generator.py` 231L + `ffmpeg_service.py` 261L + `hook_service.py` 322L: generación ASS 3-6s hook, `escape_subtitles_path`, `loudnorm`, pero **no integrado en `jobs._run_job`** (pipeline aparte `POST /clips/{id}/subtitles`).

---

## 6. Backend FastAPI (Referencia, 25+ endpoints)

**App factory** `FastAPI(redirect_slashes=False)` + `lifespan` + `CORSMiddleware` + `handle_options_preflight`.

| Método | Ruta | Auth | Descripción | Códigos |
|--------|------|------|-------------|---------|
| GET | `/health` | — | `{status:ok}` | 200 |
| POST | `/auth/registro` | — | `UsuarioCreate {email,password 8-128,full_name?}` | 201, 409, 422 |
| POST | `/auth/login` | — | JSON → `{access_token,bearer}` | 200, 401 |
| POST | `/auth/login/form` | — | OAuth2 form (Swagger) | 200 |
| GET | `/auth/me` | Bearer | `UsuarioRead` | 200, 401 |
| POST | `/videos` | Bearer | `multipart video+transcription` → `VideoResponse` | 201, 400 |
| GET | `/videos` | Bearer | lista usuario | 200 |
| POST | `/videos/{id}/jobs` | Bearer | crea Job `pending` + `BackgroundTasks _run_job` | 202, 403, 404 |
| GET | `/jobs/{id}` | Bearer | `JobResponse status UPPER` + `result_metadata.clips` | 200, 404 |
| GET | `/clips` | Bearer | biblioteca `q,min_score,sort_by,page,limit,video_id,status` → `ClipListResponse` | 200 |
| GET | `/clips/{id}` | Bearer | `ClipResponse` con `published_*` | 200, 404 |
| PATCH | `/clips/{id}` | Bearer | `{title,tags}` | 200 |
| DELETE | `/clips/{id}` | Bearer | borra archivo | 204 |
| GET | `/clips/{id}/descarga` | Bearer | `FileResponse` o dummy `/tmp/clip_{id}.txt` | 200 |
| POST | `/clips/{id}/publicar` + `/publish` alias | Bearer | `{platform,caption,webhook_override_url}` → `202 PUBLISHING` + `BackgroundTasks publish_clip_task` | 202, 422, 404 |
| POST | `/clips/{id}/subtitles` | Bearer | `202` `BackgroundTasks run_subtitle_pipeline` | 202 |
| GET | `/clips/{id}/subtitles/status` | Bearer | proxy ClipResponse | 200 |
| GET | `/jobs/{id}/export?format=csv\|json` | Bearer | `Content-Disposition` | 200 |
| GET | `/clips/export?format=csv\|json` | Bearer | idem | 200 |
| GET | `/metrics` + `/api/metrics` | Bearer | `total_jobs/clips/minutes, time_saved, platform_distribution, recent_activity[7]` | 200 |
| GET | `/stats/summary` | Bearer | `total_videos/clips, avg_score, score_distribution, time_saved, recent_job` | 200 |
| GET | `/users/me`, `/me`, `/api/users/me` | Bearer | `UserResponse` | 200 |
| PUT/PATCH | `/users/me`, `/me` | Bearer | `UserUpdate` | 200, 409 |
| POST | `/users/me/change-password` | Bearer | `{current,new} 8-128` | 200 |

- **Jobs fallback:** `_run_job` intenta `run_clip_engine`; si excepción `logger.exception` → `_fallback_result()` con 2 clips → `COMPLETED` (no `FAILED` salvo fatal doble-fallback). Si 0 clips → fallback. `result_metadata.fallback=true`.
- **Publish:** `publish_service.py:publish_clip_task` `PUBLISHING` → webhook `PUBLISH_WEBHOOK_URL` o simula `2s` + `PUBLISHED` + `social_post_url https://tiktok.com/@clipsai/video/{fakeId}` + log `✓ PUBLISHED`.

---

## 7. Backend Express (Paridad ~100% Issues 3,4,5 + Publish)

**Estructura:** `src/app.ts` `cors 3000/3001/5173` + `src/db/index.ts` `pg.Pool` normaliza `postgresql+psycopg2://` + `middleware/auth.ts` `jwt.verify HS256`.

| Ruta | Estado vs FastAPI |
|------|-------------------|
| `POST /auth/registro,login,login/form, GET /auth/me` | ✅ bcryptjs `truncate72`, 201/409/422, HS256 60min |
| `POST /videos, GET /videos` | ✅ `multer diskStorage`, ext `mp4/mov/avi` + `txt/srt`, 500MB, `201` |
| `POST /videos/:id/jobs 202, GET /jobs/:id, GET /jobs/:id/stream SSE` | ✅ `setImmediate(runJob)` + `spawnSync python engine.py --json` (ANTHROPIC/OPENROUTER) + `fallback buildFallback()` → `completed` |
| `GET /clips (q/min_score/sort_by/page/limit/video_id/status)` + `GET/PATCH/DELETE /clips/:id` + `GET /clips/:id/descarga` + `POST /clips/:id/retrim` | ✅ `SORT_MAP`, `ILIKE`, `ensurePublishColumns`, `FileResponse` |
| `POST /clips/:id/publicar` + `/publish` alias `202` + `runPublish()` 2s + `PUBLISHED` | ✅ `ensurePublishColumns`, `UPDATE status=PUBLISHING/PUBLISHED` mayúsculas, `PUBLISH_WEBHOOK_URL` |
| `GET /jobs/:id/export, /clips/export, /metrics, /stats/summary, /users/me` | ✅ `csv/json`, `Math.round` idem |

Divergencias menores: Swagger solo FastAPI `/docs`, SSE solo Express, `retrim` solo Express. Misma DB/JWT → mismo `TOKEN` funciona en `:8000` y `:3001` (Issue #6 cerrable con evidencias).

---

## 8. Frontends (React 95% ↔ Vue 95%)

| Dimensión | React (`frontend_react`) | Vue (`frontend_vue`) |
|-----------|--------------------------|----------------------|
| Estado auth | `Context/AuthContext.tsx` `localStorage clipsai_token` + `init /auth/me` | `Pinia useAuthStore` |
| HTTP | `fetch` `lib/apiClient.ts` `Bearer` + `parseError 401/409/422` | `axios` `api/client.ts` interceptors `401→removeItem+push /login` |
| Servicios | `services/api.ts` `auth/video/job/clip/stats/metrics/export/publishClip` | `api/services.ts` + `services/api.ts` re-export |
| Router | `react-router-dom` `ProtectedLayout` → `/dashboard,/clips,/library,/upload,/jobs/:jobId,/settings` | `vue-router` `beforeEach requiresAuth` → `/dashboard,/clips,/library,/upload,/jobs/:jobId,/settings,/404` |
| Polling | `hooks/useJobPolling.ts` 2s `COMPLETED/FAILED` | `composables/useJobPolling.ts` getter |
| Páginas | `AuthPage` tabs `Login/Registro`, `UploadPage` dropzone neon dashed lime, `JobStatusPage` StatusBadge + `result_metadata.clips`, `DashboardPage` recharts BarChart + KPIs, `ClipLibraryPage+LibraryPage` duplicado, `SettingsPage` | `AuthView`, `UploadView`, `JobStatusView`, `DashboardView` barras CSS, `ClipLibraryView+LibraryView` duplicado, `SettingsView` |
| Biblioteca toolbar | `flex p-3 bg-[#121824] rounded-xl border 56px` 1 fila: search + `min_score/sort` + `grid/list` toggle | idem |
| Publish UI (Issue #12) | Modal `tiktok/instagram/youtube/webhook` + `caption 500` + `webhook_override_url` → `clipService.publishClip` → badge `PUBLISHING` amber pulse → `PUBLISHED` emerald + `Ver post` link, toast, `type="button"` + `console.log` debug | idem `<script setup>` + `ref(Platform)` |
| Build | `vite 5.3` `tsc --noEmit` | `vue-tsc --noEmit` |
| Tema | `spark.css` Cyber-Tech Dark unificado | idem |

Duplicados `LibraryPage==ClipLibraryPage` (4 ficheros), `axios` muerto en React (usa fetch), `useUploadAndProcess` muerto.

---

## 9. Flujos E2E (cómo probar)

**Sin UI (FastAPI :8000 y Express :3001 mismo JWT):**
```bash
curl -X POST http://localhost:8000/auth/registro -H "Content-Type: application/json" -d '{"email":"a@a.com","password":"Test12345!"}'
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"a@a.com","password":"Test12345!"}' | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
curl -X POST http://localhost:8000/videos -H "Authorization: Bearer $TOKEN" -F video=@river.mp4 -F transcription=@trans.txt # 201
JOB=$(curl -s -X POST http://localhost:8000/videos/$VID/jobs -H "Authorization: Bearer $TOKEN" | jq -r .id)
watch "curl -s http://localhost:8000/jobs/$JOB -H 'Authorization: Bearer $TOKEN' | jq '{status,result_metadata}'"
curl http://localhost:8000/clips -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/clips/$CLIP/publicar -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"platform":"tiktok","caption":"¡River! #RiverPlate"}' # 202 PUBLISHING → 2s → PUBLISHED
```

**UI:** `/auth` → registro/login → `/upload` dropzone → `POST /videos 201` → `POST /jobs 202` → `/jobs/:id` polling 2s `PENDING→PROCESSING→COMPLETED` → `/clips` grid/list + `Publicar` modal → `POST /clips/:id/publicar 202` → badge amarillo → verde + link.

---

## 10. Configuración (.env / .env.example)

```ini
POSTGRES_USER=clipsai
POSTGRES_PASSWORD=changeme
POSTGRES_DB=clipsai
POSTGRES_PORT=5432
POSTGRES_TZ=UTC
DATABASE_URL=postgresql+psycopg2://clipsai:changeme@db:5432/clipsai
JWT_SECRET=cambiar-por-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
APP_ENV=development

ANTHROPIC_API_KEY=sk-ant-...        # prioritario
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_API_KEY=sk-...               # fallback
OPENROUTER_API_KEY=sk-or-...        # fallback multi-model
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
DEEPSEEK_API_KEY=...
API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
MODEL=deepseek-chat

PUBLISH_WEBHOOK_URL=                # si vacío simula URL ficticia

# Frontends
VITE_API_URL=http://localhost:8000  # React/Vue
PORT=3001                           # Express
```

Docker `env_file: .env` + `environment:` interpolados. `.env` gitignored, `.env.example` con `changeme` (Issue #13 sanitización pendiente: rotar `sk-ant` filtrado en history + `git filter-repo`).

---

## 11. Docker Compose

```yaml
services:
  db: postgres:15-alpine healthcheck pg_isready, volume postgres_data, init-scripts/:docker-entrypoint-initdb.d
  backend_fastapi: build ./backend_fastapi, depends_on db healthy, ports 8000:8000, env DATABASE_URL+JWT, healthcheck curl /health
  backend_express: build ./backend_express, depends_on db healthy, ports 3001:3001, env DATABASE_URL+JWT, healthcheck node fetch /health
networks: clipsai-net
```

Falta: `frontend_react:3000` + `frontend_vue:5173` como servicios `vite preview` (ver gap).

---

## 12. Seguridad

- `bcryptjs`/`bcrypt` truncate 72 bytes, `HS256` `exp 60m` `type:access`, `HTTPBearer` 401.
- `CORS` + `OPTIONS` handler, `redirect_slashes=False` evita 307.
- Deuda: `ANTHROPIC_API_KEY` real en `git log` y `.env.example` (rotar + `BFG`), `JWT_SECRET` default `dev_secret...` en código (min 16 mitiga), `requirements.txt` tenía `passlib` muerto (ahora `+requests+python-dotenv+anthropic`), `.env` trackeado, sin `express-rate-limit`/`slowapi`, sin `ssl` en `pg.Pool`.

---

## 13. Estado Issues y Gaps → Nuevas Issues Sugeridas

| Estado | Issues |
|--------|--------|
| ✅ Completado | 1 DB, 2 engine wrapper, 3 auth, 4 videos/jobs, 5 clips CRUD, 7 React upload/job, 14 FastAPI docs, 17 dark mode, 18 toolbar |
| ⚠️ Parcial | 6 Express 35%→95% (falta Swagger + docs), 8 React publish (ahora fix audit publicación), 9 Vue 95% (recharts vs CSS), 13 seguridad/compose |
| ❌ Pendiente | 10 subtítulos burned-in (ASS listo no wireado), 11 hook teaser (hook_service listo no concat), 12 publish backend hecho pero UI badge solo 202→2s (sin SSE), 13/21 compose completo + secretos |
| 🆕 Propuestos | 15 Express full (ya casi), 16 wire motor real (ya `run_clip_engine` real + fallback), 19 subs+hook, 20 publish UI (ya), 21 seguridad+compose, 22 swagger+tests |

### Gaps detectados para nuevas issues (priorizado)

**ALTA**
- **21. Seguridad & compose completo:** rotar `ANTHROPIC_API_KEY` + `git filter-repo`, `.env.example=changeme`, `docker-compose.yml +5 servicios` (`frontend_react:3000`, `frontend_vue:5173`) `depends_on healthy`, `scripts/verify-compose.sh`, `git grep sk-ant` vacío.
- **19. Subtítulos + Hook wireado:** integrar `subtitle_pipeline` en `jobs._run_job` tras `cortar_clip` → `ffmpeg -vf subtitles=...` + `hook concat 3-6s` → `file_path` final 1080x1920, flag `ENGINE_MODE=real|mock`.
- **15. Express Swagger:** `swagger-jsdoc + swagger-ui-express` `GET /docs` OpenAPI 3.0 espejo FastAPI, `GET /api-docs` + tags.

**MEDIA**
- **20. Publish SSE + UI polling:** `GET /clips/{id}` ya devuelve `PUBLISHED`, añadir `SSE /clips/:id/stream` publish + `usePublishPolling` 1s + link `external_url` en modal.
- **8/9. Biblioteca CRUD completo:** editar/borrar/descargar desde UI (endpoints existen, falta botón `ExportDropdown` ya + `confirm delete` + `downloadUrl`).
- **Upload S3/MinIO:** reemplazar `UPLOAD_DIR local storage/uploads` por `S3` presigned.

**BAJA**
- **22. Tests & observabilidad:** `pytest test_auth/jobs/clips` + `vitest useJobPolling` + `pino/structlog` + `GET /health {uptime,db_latency}` + CI `typecheck+pytest`.
- **Perf:** paginación cursor vs offset 10k clips, `GIN` índice `tags JSONB`, `rate-limit` `express-rate-limit/slowapi`, `SSE/WebSocket` reemplaza polling 2s.
- **UX:** i18n `react-i18next/vue-i18n`, roles `admin/editor`, editor timeline drag-drop, analytics heatmap retención, multi-idioma.

### Plantilla para nueva issue

```md
## Issue N — Título
**Descripción:** problema
**Objetivo:** métrica verificable
**Alcance incluido:** archivos/endpoints/UI
**Alcance excluido:** qué no
**Dependencias:** issues previas
**Criterios:** - [ ] comando verificable
**Evidencias:** capturas, curl, video
```

**Próxima rama sugerida:** `feat/compose-completo` (5 servicios <2min) o `feat/subs-hook-wire` (fin Issues 10/11).

