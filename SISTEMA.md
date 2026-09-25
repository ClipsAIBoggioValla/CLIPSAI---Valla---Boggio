# CLIPSAI — Documentación Integral del Sistema (2026)

> **Documento maestro.** Unifica objetivo y alcance (antes `PROYECTO.md`), estructura y guía de uso (antes `README.md`) y estado/arquitectura/deuda (versión previa de este archivo). Fuentes vivas complementarias: [`ISSUES.md`](./ISSUES.md) (backlog) y [`ENGINE_USO.md`](./ENGINE_USO.md) (firma del motor).
>
> **Propósito:** describir de arriba a abajo qué es el sistema, qué hace hoy, con qué lo hace, cómo se estructura el código y qué falta — para decidir nuevas issues y onboarding.

---

## Índice

1. [Visión, objetivo y alcance](#1-visión-objetivo-y-alcance)
2. [Arquitectura de despliegue](#2-arquitectura-de-despliegue)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Modelo de datos (PostgreSQL + ORM)](#5-modelo-de-datos-postgresql--orm)
6. [Motor IA (Python)](#6-motor-ia-python)
7. [Paquete `backend/` desacoplado (contratos y tracks)](#7-paquete-backend-desacoplado-contratos-y-tracks)
8. [Backend FastAPI (referencia)](#8-backend-fastapi-referencia)
9. [Backend Express (espejo)](#9-backend-express-espejo)
10. [Frontends React / Vue](#10-frontends-react--vue)
11. [Tema y diseño Cyber-Tech Dark](#11-tema-y-diseño-cyber-tech-dark)
12. [Flujos E2E (cómo probar)](#12-flujos-e2e-cómo-probar)
13. [Variables de entorno (.env / .env.example)](#13-variables-de-entorno)
14. [Docker Compose y orquestación](#14-docker-compose-y-orquestación)
15. [Seguridad](#15-seguridad)
16. [Scripts, utilidades y testing](#16-scripts-utilidades-y-testing)
17. [Estado de Issues y roadmap](#17-estado-de-issues-y-roadmap)
18. [Plantilla para nuevas Issues](#18-plantilla-para-nuevas-issues)

---

## 1. Visión, objetivo y alcance

### 1.1 Objetivo principal

Convertir **clipsai** (motor de generación automática de clips virales a partir de video largo) en un sistema web completo: los usuarios suben un video, el sistema lo procesa de forma asíncrona con el pipeline existente (detección por audio + IA + FFmpeg), le añade **subtítulos quemados dinámicos**, antepone un **hook inicial de alta energía**, y permite gestionar y **publicar automáticamente los clips** en redes sociales (TikTok, Instagram Reels, YouTube Shorts) mediante OAuth 2.0, con autenticación JWT e interfaz web.

Automatiza el trabajo de un editor de clips: detectar momentos con mayor potencial de retención/viralidad combinando **análisis de audio** (energía, cambios bruscos, clustering) + **LLM sobre transcripción** y recortar automáticamente con FFmpeg.

### 1.2 Flujo canónico

```
Video (.mp4/.mov/.avi) + Transcripción (.txt/.srt)
→ POST /videos (multipart) → POST /videos/{id}/jobs (202)
→ Job pending→processing→completed (+ clips con ASS + hook)
→ GET /clips (biblioteca) → PATCH/DELETE/descarga
→ POST /clips/{id}/publicar (202 → PUBLISHING → PUBLISHED) → badge verde + URL
→ /stats, /metrics, /export (csv/json), /docs
```

### 1.3 Límites del sistema

**✅ Dentro del alcance:**
- Pipeline de detección de momentos virales (análisis de audio + IA sobre transcripción)
- Generación de clips verticales 1080x1920 (9:16) listos para publicar
- Subtitulado automático dinámico (burned-in) palabra por palabra
- Hook inicial de alta energía anteuesto al clip
- Publicación automática a redes vía OAuth 2.0 real (Issues 24–27)
- Gestión de usuarios, videos, jobs y clips vía API con autenticación JWT
- Interfaz web (subida, seguimiento, biblioteca, dashboard, integraciones)
- Persistencia en PostgreSQL dockerizada
- Dual stack: 2 backends (FastAPI y Express) con paridad de endpoints; 2 frontends (React y Vue) con paridad de vistas; misma DB y mismo JWT

**❌ Fuera de alcance:**
- Procesamiento de streams en vivo / tiempo real
- Compositor multi-cámara para podcast o layout específico gaming
- Aplicación móvil nativa
- Edición manual de clips dentro del sistema (timeline)
- Subtitulado o doblaje fuera del español
- Arquitectura distribuida multi-servidor (un solo host vía `docker-compose`)

### 1.4 Alcances funcionales y no funcionales

**Funcionales:**
- Registro e inicio de sesión con JWT (JSON y form OAuth2 para Swagger)
- Subida de video con transcripción; disparo asíncrono de `Job` con consulta de estado
- Detección de momentos por audio (RMS, eventos) + IA sobre la transcripción
- Subtítulos quemados sincronizados + hook inicial (Issue 29)
- Publicación real a TikTok/Instagram/YouTube (Issues 24–28)
- CRUD de `Clip` (listar, editar metadata, eliminar, descargar, exportar)
- Dashboard con métricas, metrics de 7 días y export CSV/JSON

**No funcionales:**
- **Seguridad:** bcrypt (truncate 72 bytes), JWT HS256, secretos en variables de entorno (ver deuda §15)
- **Persistencia:** PostgreSQL 15 con volumen `clipsai_postgres_data`
- **Disponibilidad:** procesamiento asíncrono no bloqueante (`BackgroundTasks` / `setImmediate`)
- **Mantenibilidad:** paridad verificable entre backends/frontends; motor desacoplado de la capa web
- **Desplegabilidad:** `docker compose up -d --build` levanta los 6 servicios

### 1.5 Objetivos específicos y medibles

1. 2 backends con paridad de endpoints sobre `Usuario`, `Video`, `Job`, `Clip`
2. 2 frontends con las mismas vistas (login, upload, jobs, clips, publicación, integraciones)
3. Subtítulos automáticos burned-in sincronizados en cada clip
4. Selección y anteposición automática de hook inicial
5. Módulo y endpoint de publicación automática a redes
6. Mantener intacta la lógica de detección ya validada
7. Documentar API con OpenAPI/Swagger en ambos backends
8. Eliminar secretos hardcodeados y moverlos a `.env`

---

## 2. Arquitectura de despliegue

```
              ┌──────────────────────────────────────────────┐
 React :3000 ─┤                                              ├─┐
 Vue :5173  ──┤  FastAPI :8000                               │ ▼
              │  /auth /auth/social /videos /jobs /clips     │  PostgreSQL :5432
              │  /publish /subtitles /export /metrics        │  (volume clipsai_postgres_data,
              │  /stats /users /docs (Swagger)               │   init-scripts/*.sql, healthcheck)
              │  + retrim/stream (paquete backend/)          │  ▲
              └──────────────┬───────────────────────────────┘  │
                             │ BackgroundTasks                  │
                             ▼                                  │
              ┌──────────────────────────────┐                 │
              │ Motor IA (Python)            │─────────────────┘
              │ engine.py → main.py          │
              │ librosa + faster-whisper     │
              │ + Claude/OpenRouter/DeepSeek │
              │ + FFmpeg (ASS + hook)        │
              └──────────────────────────────┘

 Express :3001 ──► misma DB + mismo JWT (HS256) ──► spawnSync python engine.py --json
 ngrok ──────────► https://api.clipsai.xyz → backend_fastapi:8000  (callbacks OAuth, inspect :4040)
```

- **Red:** `clipsai-net` bridge.
- **Volumen:** `clipsai_postgres_data` persiste `down`/`up`; `./storage` montado en FastAPI (`/app/storage` y `/storage`) para clips y uploads.
- **Healthchecks:** `db pg_isready`, `fastapi curl /health`, `express node fetch /health`.
- **CORS:** orígenes `localhost/127.0.0.1` 3000/3001/5173 + `https://api.clipsai.xyz` + regex `*.ngrok-free.dev|*.clipsai.xyz`, con middleware OPTIONS manual en FastAPI.
- **Async:** `BackgroundTasks` (FastAPI) / `setImmediate` (Express). Migrable a Celery/Redis si `REDIS_URL`.
- **Túnel HTTPS:** servicio `ngrok` en compose con dominio permanente `api.clipsai.xyz` (Issue 23) — requerido para callbacks OAuth.

---

## 3. Stack tecnológico

| Capa | Tech | Notas |
|------|------|-------|
| Orquestación | Docker + Compose v2 + `start-dev.ps1` | 6 servicios, healthchecks |
| DB | PostgreSQL 15 + `uuid-ossp` | triggers `updated_at`, CHECK `lower()` case-insensitive |
| Backend #1 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 sync + Pydantic 2 + python-jose + bcrypt + uvicorn | `redirect_slashes=False`, lifespan migrations |
| Backend #2 | Node 20 + Express 4.19 + pg 8.11 + jsonwebtoken + bcryptjs + multer + tsx + TS 5.5 + swagger-jsdoc | `type:module`, pool normaliza `postgresql+psycopg2://` |
| Frontend #1 | React 18.3 + TS 5.5 + react-router 6 + Context + Tailwind 3.4 + Vite 5.3 + recharts | `fetch` apiClient, `useJobPolling` 2s |
| Frontend #2 | Vue 3.4 + TS 5.5 + vue-router 4 + Pinia 2 + Axios + Tailwind 3.4 + Vite 5.3 | interceptors 401→/login, composable polling |
| Motor IA | Python + librosa + faster-whisper large-v3-turbo + scikit-learn KMeans + Anthropic/OpenAI/OpenRouter/DeepSeek + FFmpeg | pipeline `extraer_audio→analizar→formatear→enriquecer→LLM→validar→cortar` |
| Contratos | Paquete `backend/core` (Pydantic + ABCs) | handoff tipado track A ↔ track B |
| Estilos | Tailwind + `spark.css` Cyber-Tech Dark | `#0B0F17` bg, `#080C14` sidebar, `#121824` card, `#B4F105` lime glow |
| Otros | `requests`, `python-dotenv`, `anthropic`, `swagger-ui-express` | OAuth YouTube/Instagram/TikTok |

---

## 4. Estructura del repositorio

### 4.1 Árbol completo (sin `node_modules`, `dist`, `__pycache__`)

```
.
├── SISTEMA.md                   # ← ESTE documento maestro
├── ISSUES.md                    # backlog vivo (Issues 1–35, estado GitHub)
├── ENGINE_USO.md                # guía firma procesar_video + errores + CLI
│
├── .env                         # variables reales (gitignored) — ver .env.example
├── .env.example                 # plantilla (⚠️ contiene key filtrada, ver §15)
├── docker-compose.yml           # 6 servicios: db, 2 backends, 2 frontends, ngrok
├── start-dev.ps1                # orquestación híbrida/docker (-Docker, -Down, -Logs)
├── package.json / package-lock.json
│
├── init-scripts/
│   ├── 01-init-schema.sql       # DDL: usuarios, videos, jobs, clips + triggers + índices
│   ├── 02-social-accounts.sql   # DDL: social_accounts (OAuth) — Issue 22
│   └── README.md
│
├── backend/                     # Paquete desacoplado (contratos + tracks paralelos)
│   ├── README.md                # guía de tracks A/B
│   ├── core/
│   │   ├── schemas.py           # WordToken, TranscriptData, ViralClipCandidate, RenderConfig,
│   │   │                        # ScheduledPost, AudioFeatures, AutopilotJob(+Status)
│   │   ├── interfaces.py        # ABCs ITranscriber, IAudioAnalyzer, IIngestionService,
│   │   │                        # IViralityEngine, IRenderer, IPublisher, IJobOrchestrator
│   │   └── security/
│   ├── api/routes/
│   │   ├── retrim.py            # POST /clips/{id}/retrim (montado en FastAPI si importa)
│   │   └── stream.py            # GET /jobs/{id}/stream SSE
│   ├── track_a/                 # ingestion, audio/analyzer, transcription/stt
│   ├── track_b/                 # virality/engine, rendering/ffmpeg+captions, publishing/scheduler
│   ├── services/ core/shared/ tests/
│
├── backend_fastapi/             # Backend #1 (referencia)
│   ├── Dockerfile               # python:3.11-slim + ffmpeg + curl, non-root appuser, uvicorn :8000
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # app + lifespan (ALTER TABLE) + CORS + routers + /health
│       ├── config.py            # Settings (DATABASE_URL auto host, JWT, OAuth, LLM keys)
│       ├── database.py deps.py
│       ├── models/              # usuario, video, job, clip, social_account
│       ├── schemas/             # usuario, video, job, clip, stats, metrics, token
│       ├── security/            # hashing.py (bcrypt nativo), jwt.py (HS256)
│       ├── routers/             # auth, videos, jobs, clips, export, metrics, stats,
│       │                        # users, publish, subtitles, social_auth
│       ├── services/            # engine, ass_generator, ffmpeg_service, hook_service,
│       │                        # whisper_service, publish_service, tiktok|youtube|instagram_service,
│       │                        # claude_service, llm_service
│       ├── tasks/subtitle_pipeline.py
│       └── api/v1/endpoints/subtitles.py
│
├── backend_express/             # Backend #2 (espejo ~100%)
│   ├── Dockerfile / package.json / tsconfig.json
│   └── src/
│       ├── index.ts app.ts      # cors + mounts + Swagger /docs + /openapi.json
│       ├── db/index.ts          # pg.Pool normaliza URL
│       ├── middleware/auth.ts   # jwt.verify HS256
│       ├── docs/swagger.ts      # OpenAPI 3.0 (Issue 30)
│       └── routes/              # auth, videos, jobs, clips, export, metrics, stats, users, publish
│
├── frontend_react/              # Frontend #1
│   ├── vite.config.ts (port 3000) / tailwind.config.js / package.json
│   └── src/
│       ├── main.tsx App.tsx     # rutas: /auth, /dashboard, /clips, /upload, /jobs/:jobId,
│       │                        # /settings, /dashboard/integrations, /settings/integrations
│       ├── context/AuthContext.tsx
│       ├── lib/apiClient.ts     # fetch + Bearer + parseError
│       ├── services/api.ts      # auth/video/job/clip/stats/metrics/export/publishClip
│       ├── hooks/useJobPolling.ts (2s) + useUploadAndProcess.ts (sin uso)
│       ├── components/          # Layout, Sidebar, Navbar, Avatar, ProfileMenu, Footer,
│       │                        # ProtectedRoute, ExportDropdown
│       ├── pages/               # AuthPage, UploadPage, JobStatusPage, DashboardPage,
│       │                        # ClipLibraryPage, LibraryPage (duplicado), SettingsPage,
│       │                        # IntegrationsPage, settings/IntegrationsSettings
│       ├── styles/spark.css     # tokens Cyber-Tech Dark
│       └── types/api.ts
│
├── frontend_vue/                # Frontend #2 (paridad 1:1)
│   ├── vite.config.ts (port 5173) / package.json
│   └── src/
│       ├── main.ts App.vue router/index.ts (guards + VITE_ALLOW_ANONYMOUS)
│       ├── stores/auth.ts       # Pinia
│       ├── api/client.ts (axios + interceptors) + api/services.ts
│       ├── composables/useJobPolling.ts
│       ├── components/          # Layout, Sidebar, Navbar, Avatar, ExportDropdown, Footer
│       ├── views/               # Auth, Upload, JobStatus, Dashboard, ClipLibrary,
│       │                        # Library (duplicado), Settings, Integrations, NotFound
│       ├── assets/spark.css     # idéntico a React
│       └── types/api.ts
│
├── main.py                      # Pipeline monolítico (~1004L): LLM, prompt viral, validar, cortar
├── audio_analyzer.py            # 372L: librosa RMS + eventos + KMeans → audio.json / momentos_virales.json
├── whisper_transcriber.py       # 261L: faster-whisper large-v3-turbo + parseo YouTube
├── editor_viral.py              # 292L: VideoEditor vertical 1080x1920 + face crop + loudnorm
├── engine.py                    # 378L: wrapper estable procesar_video → ProcesamientoResultado
├── engine_subprocess.py         # 183L: wrapper subprocess timeout 600s
├── ejemplo_engine.py            # ejemplo de invocación
├── limpiar.py                   # borra artefactos temporales
├── ENGINE_USO.md                # documentación del wrapper
│
├── storage/                     # clips renderizados + uploads + sample_test.mp4
├── gaming_procesado/            # salida de ejemplo (audio.json, momentos_virales.json, clips/)
├── spark-admin-1.0.0/           # plantilla visual de referencia
├── scripts/                     # verify-auth.sh, verify-db.sh, verify-issue4/5.sh,
│                                # test_hooks.py, test_subtitles.py
├── tests/                       # fixtures
├── docs/design-reference.md     # tokens spark-admin
├── .github/CODEOWNERS
└── (fixtures raíz: transcripcion_test.txt, test_audio.wav, whisper_words.json)
```

### 4.2 Archivos que responden a "¿dónde está X?"

| Necesidad | Archivo |
|---|---|
| Objetivo/alcance | §1 de este documento |
| Pipeline de clips | `main.py` + `engine.py` |
| Análisis de audio | `audio_analyzer.py` |
| Transcripción | `whisper_transcriber.py` + `backend_fastapi/app/services/whisper_service.py` |
| Subtítulos ASS | `backend_fastapi/app/services/ass_generator.py` + `ffmpeg_service.burn_subtitles` |
| Hook teaser | `backend_fastapi/app/services/hook_service.py` + `ffmpeg_service.build_hook_clip` |
| Publicación real | `backend_fastapi/app/services/publish_service.py` + `tiktok|youtube|instagram_service.py` |
| OAuth connectors | `backend_fastapi/app/routers/social_auth.py` |
| Contratos compartidos | `backend/core/schemas.py` + `interfaces.py` |
| Backlog | `ISSUES.md` |

---

## 5. Modelo de datos (PostgreSQL + ORM)

### 5.1 Esquema relacional

```
usuarios 1──N videos 1──N jobs 1──N clips
usuarios 1──N social_accounts (OAuth YouTube/Instagram/TikTok)
```

| Tabla | Columnas clave | Constraints / Índices |
|-------|---------------|----------------------|
| **usuarios** | `id UUID PK`, `email UNIQUE`, `hashed_password`, `full_name`, `avatar_url VARCHAR(500)`, `theme_preference VARCHAR(20) DEFAULT 'dark'`, `created_at/updated_at` | trigger `set_updated_at()`, índice email |
| **videos** | `id UUID PK`, `usuario_id FK CASCADE`, `original_filename`, `file_path`, `transcription_filepath`, `transcript TEXT (50k)`, `duration_seconds FLOAT`, `created_at` | `idx_videos_usuario_id` |
| **jobs** | `id UUID PK`, `video_id FK CASCADE`, `status pending/processing/completed/failed` (via `lower()` CHECK), `progress INTEGER 0-100` (`chk_jobs_progress`), `result_metadata JSONB`, `error_message` | `idx_jobs_video_id`, `chk_jobs_status` |
| **clips** | `id UUID PK`, `job_id FK CASCADE`, `video_id`, `title`, `file_path`, `start_time/end_time FLOAT` (`chk_time_range`), `score DOUBLE`, `tags JSONB`, `status` (`ready/PUBLISHING/PUBLISHED/FAILED`), `publication_status` (`draft/scheduled/published/failed/not_published/publishing` via `lower()`), `social_network`, `published_platform`, `social_post_id/url`, `published_at`, `error_log` | `idx_clips_job_id` |
| **social_accounts** | `id UUID PK`, `user_id FK CASCADE`, `platform` (`youtube/instagram/tiktok` CHECK), `platform_account_id`, `platform_username`, `access_token`, `refresh_token`, `token_expires_at`, `account_name`, timestamps | `UNIQUE(user_id, platform)`, índices user/platform, trigger `set_updated_at()` — `init-scripts/02-social-accounts.sql` |

### 5.2 Migraciones runtime (`backend_fastapi/app/main.py` lifespan)

Idempotente, sin Alembic:
- `Base.metadata.create_all` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (videos transcription/transcript/duration, jobs result_metadata/error_message/progress, clips video_id/score/tags/status/updated_at/error_log/published_*, usuarios avatar/theme, social_accounts account_name).
- Recrea `chk_jobs_status` y `chk_clips_publication_status` / `chk_clips_social_network` como `lower(...) IN (...)` para aceptar mayúsculas.
- **Limpieza de jobs huérfanos al arrancar:** jobs en `processing` → `failed` ("Proceso interrumpido por reinicio").
- Express ejecuta `ensurePublishColumns()` fire-and-forget.

### 5.3 Entidades Pydantic / ORM

- `Clip.status` computado `"PUBLISHING"|"PUBLISHED"|"FAILED"|"ready"`; `publication_status` espejo.
- `ClipResponse` expone `published_platform/social_post_id/url/published_at`.
- `JobResponse`: `status` en mayúsculas + `result_metadata.clips[]` + `progress`.

### 5.4 JWT

- `HS256`, `JWT_SECRET` min 16 chars (default de desarrollo en `config.py`), `JWT_EXPIRE_MINUTES=1440`, payload `{sub: UUID, iat, exp, type: access}`.
- `HTTPBearer` → 401. Login doble: `POST /auth/login` (JSON) y `POST /auth/login/form` (OAuth2, útil para Swagger Authorize). Alias compat `POST /login`, `POST /registro`.

---

## 6. Motor IA (Python)

### 6.1 Pipeline (`main.py` ~1004L + `engine.py` 378L + `engine_subprocess.py`)

1. **Validación + FFmpeg check** + `tempfile.mkdtemp(prefix=clipsai_)`.
2. **Extraer audio** `ffmpeg -y -i video -q:a 0 -map a audio.mp3`.
3. **Analizar audio** `audio_analyzer.analizar_audio`: RMS (frame 2048, hop 512) → eventos grito/silencio/cambio_brusco → momentos intensos (ventana 5) → onsets/scene changes → limpiar 2s → normalizar 0-10 → KMeans 10 clusters → `audio.json` + `momentos_virales.json` (top 50 por intensidad).
4. **Formatear transcripción** regex `HH:MM:SS - Texto` → `transcripcion_formatted.txt`.
5. **Preparar para IA** comprime a ≤150 segmentos.
6. **Enriquecer** correlación audio↔transcripción por distancia <30s.
7. **Prompt + LLM** `construir_prompt`: experto viral rioplatense, 6 criterios pesados (revelación 10, controversia 9, dato 8, emocional 7, técnico 6, predicción 5), señales de audio (+1 si intensidad>7), reglas 30-90s óptimo 45-70s, output JSON `[{inicio,fin,duracion,score,criterio_principal,titulo_sugerido,hook_texto,primer_segundo,motivo,tipo_contenido,audio_score}]`.
   - Prioridad de proveedor: `ANTHROPIC_API_KEY` → `OPENROUTER_API_KEY` → `OPENAI_API_KEY` → `DEEPSEEK_API_KEY`. Reintentos `2*intento` + manejo 429; fallback entre proveedores.
   - Si LLM falla: `_mock_hooks` / `_fallback_result` determinístico → job `COMPLETED` con `result_metadata.fallback=true` (no `FAILED` salvo doble fallo).
8. **Validar clips** filtra 30-90s, score≥5, top10, sort score desc.
9. **Cortar** `ffmpeg -ss inicio -i video -t duracion -c:v libx264 ultrafast crf18 -c:a aac -movflags +faststart` → `clips/clip_i.mp4` + `clips_info.json`.
10. **Wrapper** `engine.py:procesar_video() → ProcesamientoResultado {exito, clips: ClipInfo[], carpeta_salida, error, error_tipo, error_detalle}` con manejo granular `ValidacionError|DependenciaError|AudioError|TranscripcionError|PreparacionIAError|IAError|ConexionError|TimeoutError|GeneracionError|SinClipsValidos|ImportError|ErrorInterno`. CLI `python engine.py video transcripcion --json`. Documentación completa en `ENGINE_USO.md`.

### 6.2 Servicios backend (render y publicación)

| Servicio | Función |
|---|---|
| `services/engine.py` | `run_clip_engine()` — invoca `engine.procesar_video` real; copia clips a `storage/clips/{job_id}/` |
| `services/whisper_service.py` | faster-whisper large-v3-turbo, `cuda/float16` else `cpu/int8`, `vad_filter`, beam 5 |
| `services/ass_generator.py` | `generate_hooked_ass` — ASS PlayRes 1080x1920, word-level, shift por hook |
| `services/ffmpeg_service.py` | `cut_segment`, `burn_subtitles` (`-vf subtitles=`), `build_hook_clip` (hook 3-6s), `loudnorm` |
| `services/hook_service.py` | `detect_hooks` (LLM) + fallback `_mock_hooks` |
| `tasks/subtitle_pipeline.py` | pipeline de subtitulado bajo demanda (`POST /clips/{id}/subtitles`) |
| `services/publish_service.py` | `publish_clip_task`: PUBLISHING → OAuth upload → PUBLISHED + `social_post_url`; webhook fallback `PUBLISH_WEBHOOK_URL` |
| `services/tiktok_service.py` | Content Posting API: `open.tiktokapis.com/v2/post/publish/video/init` FILE_UPLOAD + PKCE |
| `services/youtube_service.py` | Google Data API v3 upload + OAuth `state` |
| `services/instagram_service.py` | Instagram Graph API: container → poll FINISHED → publish |
| `services/claude_service.py` / `llm_service.py` | selección semántica de clips/títulos |

**Integración en jobs:** `routers/jobs.py` (`_run_job` / `run_job_safely`) con `ENABLE_ASS_HOOK = True` (100% real, sin modo simulación): engine real → por cada clip `_render_clip_with_ass_and_hook` (hook + subtítulos) con fallback degradado a corte simple si Whisper/FFmpeg falla (`tags["_render_error"]`), y `job.progress` 0-100. `_resolve_storage_dir()`: `STORAGE_CLIPS_DIR` → `/app/storage/clips` (Docker) → `<repo>/storage/clips`.

### 6.3 Utilidades de la raíz

- `whisper_transcriber.py`: `parsear_transcripcion_youtube` + `transcribir_video`.
- `editor_viral.py`: `VideoEditor` — 1080x1920 fps30, crop por haarcascade, loudnorm `I=-16 TP=-1.5 LRA=11`.
- `limpiar.py`: borra audio.mp3/.wav, audio.json, momentos_virales, clips/, __pycache__.

---

## 7. Paquete `backend/` desacoplado (contratos y tracks)

Guía completa en `backend/README.md`. Diseñado para dos devs en paralelo sin bloqueos:

```
backend/
  core/           ← Única zona compartida: contratos, no lógica
    schemas.py    ← Pydantic: WordToken, TranscriptData, AudioFeatures,
    │               ViralClipCandidate (+ViralReport), RenderConfig, ScheduledPost,
    │               AutopilotJob (+AutopilotJobStatus con 9 estados)
    interfaces.py ← ABCs: ITranscriber, IAudioAnalyzer, IIngestionService,
    │               IViralityEngine, IRenderer, IPublisher, IJobOrchestrator
  track_a/        ← ingestion (video→video_id), audio analyzer, transcription STT
  track_b/        ← virality engine, rendering ffmpeg/captions, publishing scheduler
  shared/         ← config y utilidades sin dominio
  api/routes/     ← retrim.py (POST /clips/{clip_id}/retrim),
                    stream.py (GET /jobs/{job_id}/stream SSE)
```

**Reglas:** solo `core` es compartido (PR + review de ambos); track A nunca importa track_b ni viceversa; stubs mock compilan sin FFmpeg ni API keys; handoff tipado A→B (`TranscriptData`+`AudioFeatures`) y salida a redes (`ScheduledPost`).

**Integración actual:** `backend_fastapi/app/main.py` resuelve la raíz del repo e importa condicionalmente `backend.api.routes.retrim` y `stream` (`try/except` → `None` si no existen), montándolos si el import tiene éxito. Pendiente: que ambos backends importen `backend.core.schemas` en vez de sus schemas duplicados.

**SSE de jobs** (`stream.py`): mapea `pending→0%`, `processing→55% scoring`, `completed/failed→100%` sobre `AutopilotJobStatus`.

---

## 8. Backend FastAPI (referencia)

**App factory:** `FastAPI(redirect_slashes=False)` + `lifespan` (migraciones + limpieza huérfanos) + `CORSMiddleware` + middleware `handle_options_preflight` + `@on_event startup` log de rutas. Raíz: `backend_fastapi/app/main.py`.

### 8.1 Endpoints

| Método | Ruta | Auth | Descripción | Códigos |
|--------|------|------|-------------|---------|
| GET | `/health` | — | `{status:ok}` | 200 |
| POST | `/auth/registro` | — | `UsuarioCreate {email,password 8-128,full_name?}` | 201, 409, 422 |
| POST | `/auth/login` | — | JSON → `{access_token, bearer}` | 200, 401 |
| POST | `/auth/login/form` | — | OAuth2 form (Swagger Authorize) | 200 |
| GET | `/auth/me` | Bearer | `UsuarioRead` | 200, 401 |
| POST | `/login`, `/registro` | — | alias compat (fuera de schema) | 200/201 |
| POST | `/videos` | Bearer | `multipart video (.mp4/.mov/.avi ≤500MB) + transcription (.txt/.srt)` | 201, 400 |
| GET | `/videos` | Bearer | lista usuario `created_at DESC` | 200 |
| POST | `/videos/{id}/jobs` | Bearer | crea Job `pending` + `BackgroundTasks run_job_safely` | 202, 403, 404 |
| GET | `/jobs/{id}` | Bearer | `JobResponse status UPPER + progress + result_metadata.clips` | 200, 404 |
| GET | `/clips` | Bearer | `q, min_score 0-100, sort_by, page, limit 1-100, video_id, status, job_id` | 200 |
| GET | `/clips/{id}` | Bearer | `ClipResponse` con `published_*` | 200, 404 |
| PATCH | `/clips/{id}` | Bearer | `{title, tags}` | 200, 404 |
| DELETE | `/clips/{id}` | Bearer | borra archivo físico | 204, 404 |
| GET | `/clips/{id}/descarga` | Bearer | `FileResponse` o dummy | 200 |
| POST | `/clips/{id}/publicar` + `/publish` | Bearer | `{platform, caption, webhook_override_url}`; platforms `tiktok/instagram/youtube/webhook` → BackgroundTasks | 202, 422, 404 |
| GET | `/clips/{id}/publish-stream` | Bearer | SSE `PUBLISHING→PUBLISHED/FAILED` (poll 1s, timeout 90s, events `data/done/error/timeout`) | 200 |
| POST | `/clips/{id}/subtitles` | Bearer | dispara `run_subtitle_pipeline` | 202, 409 |
| GET | `/clips/{id}/subtitles/status` | Bearer | proxy ClipResponse | 200 |
| GET | `/jobs/{id}/export?format=csv\|json` | Bearer | `Content-Disposition` (+ alias `/api/v1/...`) | 200, 422 |
| GET | `/clips/export?format=csv\|json` | Bearer | idem | 200 |
| GET | `/metrics` + `/api/metrics` | Bearer | `total_jobs/clips/minutes, time_saved, platform_distribution, recent_activity[7]` | 200 |
| GET | `/stats/summary` | Bearer | `total_videos/clips, avg_score, score_distribution, time_saved, recent_job` | 200 |
| GET/PUT/PATCH | `/users/me`, `/me` (+ `/api` prefix) | Bearer | perfil; PUT `UserUpdate` | 200, 409 |
| POST | `/users/me/change-password`, PUT `/me/password` | Bearer | `{current, new} 8-128` | 200, 400 |
| GET | `/auth/social/status` (+ `/accounts`) | Bearer | integraciones conectadas | 200 |
| DELETE | `/auth/social/{platform}` | Bearer | desconectar cuenta | 200 |
| GET | `/auth/social/youtube/connect` `/callback` | — / Bearer | OAuth Google Data API v3 | 302 |
| GET | `/auth/social/instagram/connect` `/callback` | — / Bearer | OAuth Meta Graph | 302 |
| GET | `/auth/social/tiktok/connect` `/callback` | — / Bearer | OAuth TikTok PKCE | 302 |
| POST | `/clips/{id}/retrim` | Bearer | re-corte de clip (desde `backend/`) | 200 |
| GET | `/jobs/{id}/stream` | Bearer | SSE progreso de job (desde `backend/`) | 200 |

### 8.2 Detalles clave

- **Jobs:** `_run_job`/`run_job_safely` → `run_clip_engine` real → render ASS+hook → clips en `storage/clips/{job_id}/`; excepción → `_fallback_result()` (2 clips, `COMPLETED`, `fallback=true`); 0 clips → fallback.
- **Docs:** `/docs` (Swagger), `/redoc`, `/openapi.json` auto-generado desde Pydantic. Título `clipsai — FastAPI backend`, versión `0.1.0`.
- **Config:** `config.py` carga `.env` de raíz y de `backend_fastapi/`, resuelve host de DB (`db`↔`localhost` según `/.dockerenv`), y normaliza redirects OAuth para usar `PUBLIC_BACKEND_URL`.

---

## 9. Backend Express (espejo ~100%)

**Estructura:** `src/app.ts` (cors, mounts, Swagger) + `src/db/index.ts` (pg.Pool, normaliza `postgresql+psycopg2://`) + `src/middleware/auth.ts` (jwt.verify HS256, mensajes "Token expirado/inválido") + `src/docs/swagger.ts` (OpenAPI 3.0, Issue 30).

| Ruta | Implementación |
|------|----------------|
| `POST /auth/registro` `201/409` | bcryptjs truncate72 |
| `POST /auth/login`, `/auth/login/form` | HS256 60/1440min |
| `GET /auth/me` | authMiddleware |
| `POST /videos` (multer diskStorage, mp4/mov/avi + txt/srt, 500MB) `201` | `routes/videos.ts` |
| `GET /videos` | lista usuario |
| `POST /videos/:videoId/jobs` `202` | `setImmediate(runJob)` + `spawnSync python engine.py --json` (selección de proveedor por env) + fallback `buildFallback()` → `completed` |
| `GET /jobs/:jobId` | status + metadata |
| `GET /jobs/:jobId/stream` | SSE progreso |
| `GET /clips` (`q, min_score, sort_by, page, limit, video_id, status`) | `SORT_MAP`, `ILIKE` |
| `GET/PATCH/DELETE /clips/:clipId` | ownership |
| `GET /clips/:clipId/descarga` | FileResponse / dummy |
| `POST /clips/:clipId/retrim`, `/re-render` | re-corte / re-render |
| `POST /clips/:clipId/publicar` + `/publish` `202` | `runPublish()` 2s → `PUBLISHED` o webhook real |
| `GET /clips/:clipId/publish-stream`, `/clips/:clipId/stream` | SSE publicación |
| `GET /clips/export`, `/jobs/:jobId/export` (+ `/api/v1` alias) | csv/json |
| `GET /metrics`, `/api/metrics` | cálculo idéntico FastAPI |
| `GET /stats/summary` | idem |
| `GET/PUT/PATCH /users/me`, `POST /users/me/change-password`, `PUT /me/password` | bcryptjs |
| `GET /docs`, `GET /openapi.json` | swagger-ui-express, 18 paths (Issue 30) |
| `GET /health` | `{status:ok}` |

**Divergencias:** Swagger en ambos (paridad tras Issue 30); SSE de jobs/publish en ambos; `re-render/retrim` propios de Express; validación de UUID (FastAPI 422 vs Express posible 500 si formato inválido en algunas rutas). Mismo `TOKEN` funciona en `:8000` y `:3001` (misma DB + mismo `JWT_SECRET`).

**Comandos:** `npm run dev` (tsx watch), `npm run build`, `npm run typecheck`, `npm start`.

---

## 10. Frontends React / Vue

### 10.1 Paridad (≈95%)

| Dimensión | React (`frontend_react`) | Vue (`frontend_vue`) |
|-----------|--------------------------|----------------------|
| Estado auth | `Context/AuthContext.tsx` + `localStorage clipsai_token` + init `/auth/me` | Pinia `useAuthStore` |
| HTTP | `fetch` `lib/apiClient.ts` Bearer + `parseError 401/409/422` | `axios` interceptors `401→/login` |
| Servicios | `services/api.ts` (auth/video/job/clip/stats/metrics/export/publish) | `api/services.ts` |
| Router | `react-router-dom` + `ProtectedLayout` | `vue-router` `beforeEach` `requiresAuth` |
| Polling | `hooks/useJobPolling.ts` 2000ms | `composables/useJobPolling.ts` |
| Modo anónimo | `VITE_ALLOW_ANONYMOUS=true` permite Layout sin user | idem en guard |
| Build | `tsc --noEmit` / `tsc -b && vite build` | `vue-tsc --noEmit` |

**Rutas (ambos):** `/auth`, `/login→/auth`, `/`→`/dashboard`, `/dashboard`, `/clips`, `/library` (Vue; React alias borrado a `/dashboard`), `/upload`, `/jobs/:jobId`, `/settings`, `/dashboard/integrations`, `/settings/integrations`, `/404` (Vue), `*→/dashboard` (React).

### 10.2 Páginas clave

- **Auth:** tabs Login/Registro, `full_name` opcional, showPassword, alerts 401/409/422, JWT en localStorage, rehidrata en F5.
- **Upload:** `max-w-3xl`, 2 dropzones `dropzone-neon` (dashed lime glow), video `.mp4/.mov/.avi` + transcript `.txt/.srt` → `POST /videos 201` → `POST /jobs 202` → `/jobs/:id`.
- **JobStatus:** polling 2s; badges PENDING ámbar, PROCESSING sky spinner, COMPLETED verde + cards (`titulo`, inicio-fin mono, `score-badge-neon`, transcript preview), FAILED rojo con `error_message`.
- **Dashboard:** KPIs `total_jobs, total_clips, time_saved_hours, avg_score`; recharts `BarChart` (React) vs barras CSS (Vue); `platform/score_distribution`; `recent_activity[7]`; empty CTA.
- **Biblioteca:** toolbar 1 fila (`flex p-3 bg-[#121824] rounded-xl`, 56px): search debounce 350ms → `?q=`, `min_score/sort_by`, toggle grid/list, paginación `page/limit 10`; modal Publicar (platform + caption 500 + `webhook_override_url`) → badge `PUBLISHING` amber pulse → `PUBLISHED` emerald + link `social_post_url`; `ExportDropdown` csv/json; delete confirm.
- **Integraciones:** `IntegrationsPage`/`IntegrationsView` + `settings/IntegrationsSettings` — conectar/desconectar YouTube/Instagram/TikTok vía `/auth/social/*/connect`, badge `Conectado` + `Ver post` (Issue 28).
- **Settings:** avatar 56px, `PUT /users/me`, change-password, preferencias theme/export_format.
- **Layout:** Sidebar `#080C14` fixed 280px (80px minimized con fix `dropdown-menu-profile` fixed left 88px), Navbar sticky con búsqueda → `/clips?q=`, Footer, `ProtectedRoute`.

### 10.3 Deuda conocida en UI

- Duplicados: `LibraryPage == ClipLibraryPage` (React) y `LibraryView == ClipLibraryView` (Vue) — 4 ficheros (Issue 35).
- `axios` muerto en React (usa fetch); `useUploadAndProcess` sin usar.
- React sin `/library` route propia (solo `/clips`); Vue sí.

---

## 11. Tema y diseño Cyber-Tech Dark

`spark.css` unificado en ambos frontends (`frontend_react/src/styles/` y `frontend_vue/src/assets/`), derivado de la plantilla `spark-admin-1.0.0` (tokens en `docs/design-reference.md`).

- **Tokens:** `--bg-app:#0B0F17`, `--bg-sidebar:#080C14`, `--bg-card:#121824`, `--border-subtle:rgba(255,255,255,0.08)`, `--text-primary:#F1F5F9`, `--text-secondary:#94A3B8`, `--brand-lime:#B4F105`, glow `0 0 20px rgba(180,241,5,0.35)`.
- **Sidebar:** link active `rgba(180,241,5,0.12)` + border + glow.
- **Navbar:** `backdrop-blur 16px`, `btn-quick-action` lime.
- **Cards:** `card-spark`, `clip-card::before` gradiente lime→emerald en hover, `kpi-card` top-line lime.
- **Forms/tables:** `form-control-custom` bg `#0B0F17` focus lime glow.
- **Botones:** `btn-custom-primary` lime + glow + hover `translateY(-1px)`.
- **Badges:** `score-badge-neon` high/mid/low (lime/amber/red), `badge-table success/pending/failed`.
- **Dropzone neon:** dashed `rgba(180,241,5,0.35)`, hover shadow 32px + radial glow.
- **Progress:** gradiente lime→emerald con shadow.

---

## 12. Flujos E2E (cómo probar)

### 12.1 Levantar el sistema

```bash
cp .env.example .env     # completar JWT_SECRET, OAuth, LLM keys, NGROK_AUTHTOKEN
# Opción A (6 servicios Docker):
docker compose up -d --build
docker compose ps        # 6 healthy
# Opción B (híbrida):
.\start-dev.ps1          # infra Docker + React/Vue locales + ngrok
.\start-dev.ps1 -Docker  # todo Docker
.\start-dev.ps1 -Down    # baja todo (mantiene postgres_data)
.\start-dev.ps1 -Logs
```

| Servicio | URL |
|---|---|
| React | http://localhost:3000 |
| Vue | http://localhost:5173 |
| FastAPI | http://localhost:8000 · Swagger `/docs` |
| Express | http://localhost:3001 · Swagger `/docs` |
| Postgres | localhost:5432 |
| Ngrok | https://api.clipsai.xyz (inspect `http://localhost:4040`) |

### 12.2 Sin UI (curl — mismo JWT para :8000 y :3001)

```bash
curl -X POST http://localhost:8000/auth/registro -H "Content-Type: application/json" \
  -d '{"email":"a@a.com","password":"Test12345!"}'
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"a@a.com","password":"Test12345!"}' | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
curl -X POST http://localhost:8000/videos -H "Authorization: Bearer $TOKEN" \
  -F video=@river.mp4 -F transcription=@trans.txt                    # 201
JOB=$(curl -s -X POST http://localhost:8000/videos/$VID/jobs -H "Authorization: Bearer $TOKEN" | jq -r .id)  # 202
watch "curl -s http://localhost:8000/jobs/$JOB -H 'Authorization: Bearer $TOKEN' | jq '{status,progress,result_metadata}'"
curl http://localhost:8000/clips -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/clips/$CLIP/publicar -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"platform":"tiktok","caption":"¡River! #RiverPlate"}'  # 202 → PUBLISHED
curl -N http://localhost:8000/clips/$CLIP/publish-stream -H "Authorization: Bearer $TOKEN"        # SSE
```

### 12.3 Con UI

`/auth` → registro/login → `/upload` dropzone → `POST /videos 201` → `POST /jobs 202` → `/jobs/:id` polling 2s `PENDING→PROCESSING→COMPLETED` → `/clips` grid/list + modal `Publicar` → badge ámbar → verde + link → `/settings/integrations` conectar OAuth → `/dashboard` KPIs.

### 12.4 Motor por CLI (fuera de Docker)

```bash
pip install -r backend_fastapi/requirements.txt
# + librosa faster-whisper scikit-learn numpy opencv-python pydub (motor)
python main.py video.mp4 transcripcion.txt
python engine.py video.mp4 transcripcion.txt --json
python ejemplo_engine.py video.mp4 transcripcion.txt
python limpiar.py
```

---

## 13. Variables de entorno

`.env.example` (raíz) — plantilla a copiar en `.env` (gitignored):

```ini
# PostgreSQL
POSTGRES_USER=clipsai
POSTGRES_PASSWORD=changeme
POSTGRES_DB=clipsai
POSTGRES_PORT=5432
POSTGRES_TZ=UTC
DATABASE_URL=postgresql+psycopg2://clipsai:changeme@db:5432/clipsai

# JWT / App
JWT_SECRET=cambiar-por-un-secreto-largo-min-16-chars   # openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
APP_ENV=development

# Motor IA (prioridad: Anthropic → OpenRouter → OpenAI → DeepSeek)
ANTHROPIC_API_KEY=...          # ⚠️ ver §15 — key filtrada en repo
ANTHROPIC_MODEL=claude-sonnet-4-20250514   # main.py default: claude-sonnet-5
ANTHROPIC_VERSION=2023-06-01
OPENAI_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
DEEPSEEK_API_KEY=
API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
MODEL=deepseek-chat

# Publicación / webhook genérico (si vacío, simula)
PUBLISH_WEBHOOK_URL=https://api.clipsai.xyz/webhooks/publish

# OAuth YouTube (Google Data API v3) — Issue 24
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://api.clipsai.xyz/auth/social/youtube/callback

# OAuth Instagram (Meta Graph) — Issue 25
INSTAGRAM_CLIENT_ID=
INSTAGRAM_CLIENT_SECRET=
INSTAGRAM_REDIRECT_URI=https://api.clipsai.xyz/auth/social/instagram/callback
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=

# OAuth TikTok (Content Posting) — Issue 26
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=https://api.clipsai.xyz/auth/social/tiktok/callback

# Backend público / túnel (Issue 23)
PUBLIC_BACKEND_URL=https://api.clipsai.xyz
BACKEND_URL=https://api.clipsai.xyz
API_BASE_URL=https://api.clipsai.xyz
FRONTEND_URL=http://localhost:3000
FRONTEND_REDIRECT_URL=http://localhost:3000
NGROK_AUTHTOKEN=
NGROK_DOMAIN=api.clipsai.xyz

# Frontends / Express
VITE_API_URL=http://localhost:8000
BACKEND_FASTAPI_PORT=8000
BACKEND_EXPRESS_PORT=3001
```

Frontends: `frontend_react/.env` y `frontend_vue/.env` → `VITE_API_URL`. Opcional `VITE_ALLOW_ANONYMOUS=true` para modo sin auth.

`config.py` de FastAPI fuerza los `*_REDIRECT_URI` a `PUBLIC_BACKEND_URL` si contienen URLs ngrok temporales.

---

## 14. Docker Compose y orquestación

`docker-compose.yml` — 6 servicios:

| Servicio | Imagen/build | Puerto | Notas |
|---|---|---|---|
| `db` | `postgres:15-alpine` | 5432 | volume `postgres_data`, `init-scripts/` read-only, healthcheck `pg_isready` |
| `backend_fastapi` | `./backend_fastapi` | 8000 | ffmpeg+curl en imagen, `./storage:/app/storage`, env LLM+OAuth, healthcheck curl |
| `backend_express` | `./backend_express` | 3001 | env DB+JWT+LLM, healthcheck node fetch |
| `frontend_react` | `node:20-alpine` | 3000 | `npm install && npm run dev --host`, hot-reload `CHOKIDAR_USEPOLLING`, `depends_on` fastapi healthy |
| `frontend_vue` | `node:20-alpine` | 5173 | idem |
| `ngrok` | `ngrok/ngrok:latest` | 4040 | `http backend_fastapi:8000 --domain=api.clipsai.xyz`, `NGROK_AUTHTOKEN` |

Red `clipsai-net` bridge; volumen nombrado `clipsai_postgres_data`. `down` conserva datos; `down -v` los borra.

`start-dev.ps1`: `-Docker` (todo compose), default (híbrido: `docker compose up -d db backend_fastapi backend_express` + frontends locales con `concurrently` + ngrok), `-Down`, `-Logs`.

---

## 15. Seguridad

**Implementado:**
- bcrypt nativo truncate 72 bytes (evita bug passlib+bcrypt4) en FastAPI; `bcryptjs` en Express.
- JWT HS256 con `type: access` y expiración; `HTTPBearer` 401; distinción `ExpiredSignatureError` vs `JWTError`.
- CORS con allowlist + regex dominios; `redirect_slashes=False` evita 307 abiertos.
- Sin secretos en código de routers/services (leen `os.environ` / `Settings`).
- Usuario no-root en Dockerfile FastAPI; límite 500MB en uploads; extensiones permitidas whitelist.

**Deuda abierta (Issue 13 / 21):**
- ⚠️ **`ANTHROPIC_API_KEY` real en `.env.example:32` y en `git history`** — requiere rotación + `git filter-repo`/`BFG` + limpieza `git grep sk-ant`.
- `JWT_SECRET` con default `dev_secret...` en `config.py` (mitigado por `min_length=16`, pero debe obligarse en prod).
- Sin `express-rate-limit` / `slowapi`.
- Sin TLS en `pg.Pool` (solo local/bridge).
- `.env` trackeado históricamente (verificar `git ls-files .env`).

---

## 16. Scripts, utilidades y testing

| Script | Uso |
|--------|-----|
| `scripts/verify-auth.sh` | curl registro/login/me |
| `scripts/verify-db.sh` | `psql \dt` + `\d` de las tablas |
| `scripts/verify-issue4.sh` | POST /videos + polling jobs |
| `scripts/verify-issue5.sh` | CRUD clips |
| `scripts/test_hooks.py`, `scripts/test_subtitles.py` | pruebas de hook y subtítulos |
| `limpiar.py` | limpia artefactos del motor |
| `start-dev.ps1` | orquestación del stack |

**Validación:**
- Typecheck frontends: `npm run typecheck` (React `tsc --noEmit`, Vue `vue-tsc --noEmit`).
- Build: `npm run build` → `dist/`.
- Express: `npm run typecheck`, `curl /health`, `curl /docs`.
- Infra: `docker compose logs -f`, `docker compose ps`, `curl :8000/health`, `curl :8000/docs`.
- Pipeline Issue 29: `test_issue_29_pipeline.py` (ffprobe 9:16, ASS PlayRes, fallback).
- Cobertura de tests automatizados aún limitada (Issue 22 propuesta: `pytest` + `vitest`).

---

## 17. Estado de Issues y roadmap

Fuente detallada: [`ISSUES.md`](./ISSUES.md) (sincronizada con GitHub, Sep 2026).

### 17.1 Resumen ejecutivo

| Estado | Cantidad | Lista |
|--------|----------|-------|
| ✅ Completado | 19 | 1, 2, 3, 4, 5, 7, 14, 17, 18, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30 (+ PR #34 Spark) |
| ⚠️ Parcial | 2 | 6 (Express ~90-100%, pulidos menores), 13 (seguridad/compose) |
| ⏳ Pendiente | 5 | 31, 32, 33, 34, 35 (GitHub #51–#55) |
| ↩️ Cerradas vía otras | 3 | 8, 9, 10/11/12 → Issues 27/28/29 |

### 17.2 Estado por área

| Área | Estado | Detalle |
|------|--------|---------|
| Infra DB + Docker | ✅ | Postgres 15 + volumen + healthcheck + DDL idempotente + 6 servicios compose |
| Motor IA | ✅ | `main.py` + wrapper `engine.py` + `engine_subprocess.py` |
| FastAPI | ✅ | ~40 rutas, auth, videos/jobs/clips, publish, subtitles, social, export, metrics, docs |
| Express | ✅ ~95% | mismas entidades + Swagger + SSE; sin `social_auth` (solo FastAPI) |
| React / Vue | ✅ ~95% | auth, upload, jobs, dashboard, biblioteca, settings, integraciones |
| Subtítulos + Hook | ✅ | Issue 29 — `ENABLE_ASS_HOOK=True` en `jobs` |
| OAuth + Publish real | ✅ | Issues 22–28 — YouTube/Instagram/TikTok |
| Docs OpenAPI | ✅ | FastAPI `/docs` + Express `/docs` + `/openapi.json` |
| Seguridad | ⚠️ | key filtrada, rate-limit ausente |
| Pendientes activas | ⏳ | SSE publish UI (31), landing (32), legales (33), video muestra (34), deuda UI (35) |

### 17.3 Issues pendientes (abiertas en GitHub)

| # | Título | Criterio clave |
|---|--------|----------------|
| 31 | SSE estado de publicación en UI | UI `PUBLISHING→PUBLISHED` sin reload (endpoint SSE ya existe) |
| 32 | Landing pública `/` | hero+features+CTA sin auth, Lighthouse SEO ≥90 |
| 33 | Páginas legales `/privacy /terms /data-deletion` | requerido para validación Meta/Google/TikTok |
| 34 | Video de muestra en `/upload` | `POST /videos/sample 201` sin multipart |
| 35 | Deuda técnica UI | eliminar `LibraryPage`/`LibraryView` duplicados, `axios` muerto, `any` en tags, `passlib` |

### 17.4 Ideas de backlog

Paginación cursor vs offset (10k clips), índice GIN `tags`, rate-limit, S3/MinIO presigned, i18n, roles admin/editor, editor timeline, analytics de retención, WebSockets en vez de polling 2s.

---

## 18. Plantilla para nuevas Issues

```md
## Issue N — Título
**Descripción:** problema
**Objetivo:** métrica verificable
**Alcance incluido:** archivos/endpoints/UI
**Alcance excluido:** qué no
**Dependencias:** issues previas
**Criterios:**
- [ ] comando verificable
**Evidencias:** capturas, curl, video
```

Convenciones: ramas `tipo/nombre-issue` desde `main`, Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:` + scope `frontend|backend|engine|infra`), PR con `Closes #N` + evidencias.

---

> **Licencia:** uso interno / académico — sin licencia pública. No subir secretos a Git. Ver `.gitignore` y `git check-ignore -v`.
>
> **Documentos relacionados:** [`ISSUES.md`](./ISSUES.md) · [`ENGINE_USO.md`](./ENGINE_USO.md) · `backend/README.md` · `docs/design-reference.md` · `init-scripts/README.md`
