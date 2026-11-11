# CLIPSAI — Documentación Integral del Sistema (2026)

> **Documento maestro.** Unifica objetivo y alcance (antes `PROYECTO.md`), estructura y guía de uso (antes `README.md`) y estado/arquitectura/deuda (versión previa de este archivo). Fuentes vivas complementarias: [`ISSUES.md`](./ISSUES.md) (backlog), [`ENGINE_USO.md`](./ENGINE_USO.md) (firma del motor) y [`docs/EVALUACION.md`](./docs/EVALUACION.md) (evaluación automática de calidad de la cátedra).
>
> **Propósito:** describir de arriba a abajo qué es el sistema, qué hace hoy, con qué lo hace, cómo se estructura el código y qué falta — para decidir nuevas issues y onboarding. Está pensado como insumo para tomar decisiones sobre los próximos pasos (ver §17.6).
>
> **Última actualización: 11 de noviembre de 2026** — Fase 1 de calidad **mergeada a `main`** (PR #104: logs DBG 0, refactor de cohesión en `editor_viral.py`, suite de 330 tests). Fase 2 en PR **#105 abierto**: fix crítico de código inalcanzable en `engine.py` (pipeline local), 395 tests, cobertura 69% agregada, `backend_express/dist/` fuera del rastreo (cierra Issue 2 del doc de seguimiento). Detalle de estado en §17.

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
17. [Estado de Issues, calidad y roadmap](#17-estado-de-issues-calidad-y-roadmap)
18. [Procesamiento serverless (RunPod + R2), despliegue y CI](#18-procesamiento-serverless-runpod--r2-despliegue-y-ci)
19. [Plantilla para nuevas Issues](#19-plantilla-para-nuevas-issues)

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

**Flujo alternativo (subida directa + GPU serverless — ver §18):** el front presigna la subida directa a Cloudflare R2 (`POST /api/videos/upload-url` → PUT presignado, sin pasar por el backend), dispara `POST /api/videos/process` y el backend delega el procesamiento (Whisper + IA + FFmpeg + render 9:16) a un **worker serverless en RunPod GPU** que devuelve los clips ya renderizados en R2 (`https://videos.clipsai.xyz/...`). El backend solo registra el resultado en la DB.

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
- Procesamiento **opcional** delegado a GPU serverless (RunPod) con almacenamiento en Cloudflare R2 y subida directa desde el navegador (§18)
- Despliegue en la nube (Render + Vercel) además de la pila local con Docker Compose

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

  ── Alternativa serverless (ver §18; activa si hay RUNPOD_API_KEY + RUNPOD_ENDPOINT_ID) ──

  Front ──PUT presign──► Cloudflare R2 (uploads/ y clips/)  ◄──PUT clips──┐
     │  POST /api/videos/upload-url + POST /api/videos/process           │
     ▼                                                                   │
  FastAPI/Express ──runsync──► RunPod Serverless GPU (worker.Dockerfile) ┘
     │                           worker: backend/handler.py → engine.py
     │                           → video_processor (9:16 + ASS + hook)
     │                           → R2 public domain videos.clipsai.xyz
     └── registra clips con url_r2 en la DB (result_metadata._source="runpod_r2")

 Express :3001 ──► misma DB + mismo JWT (HS256) ──► spawnSync python engine.py --json (local)
 Render (blueprint backend_fastapi/render.yaml) ──► disco /var/data 10GB ──► clips/uploads
 ngrok ──────────► https://api.clipsai.xyz → backend_fastapi:8000  (callbacks OAuth, inspect :4040)
```

- **Red:** `clipsai-net` bridge.
- **Volumen:** `clipsai_postgres_data` persiste `down`/`up`; `./storage` montado en FastAPI (`/app/storage` y `/storage`) para clips y uploads. En Render: disco persistente `/var/data` (10 GB) con limpieza automática (`storage_cleanup.py`, ver §18.4).
- **Healthchecks:** `db pg_isready`, `fastapi curl /health`, `express node fetch /health`.
- **CORS:** orígenes `localhost/127.0.0.1` 3000/3001/5173 + `https://api.clipsai.xyz` + regex `*.ngrok-free.dev|*.clipsai.xyz`, con middleware OPTIONS manual en FastAPI.
- **Async:** `BackgroundTasks` (FastAPI) / `setImmediate` (Express). Migrable a Celery/Redis si `REDIS_URL`.
- **Túnel HTTPS:** servicio `ngrok` en compose (legacy para dev local) con dominio permanente `api.clipsai.xyz` — requerido para callbacks OAuth. En producción el dominio lo sirve un **Cloudflare Tunnel permanente** (ver comentario en `docker-compose.yml`).
- **Procesamiento distribuido:** el motor puede correr **local** (en el backend, modo por defecto) o **delegarse a RunPod GPU** (§18). El worker no corre en compose: se publica como imagen en Docker Hub vía CI.

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
| Worker serverless | RunPod Serverless (GPU CUDA 12.1, PyTorch image) + `worker.Dockerfile` | `backend/handler.py` → `engine.procesar_video` → `video_processor` 9:16 → R2 (§18) |
| Almacenamiento | Cloudflare R2 (API S3) + dominio público `videos.clipsai.xyz` | presign SigV4 manual (`s3.ts`) o boto3 (FastAPI); subida directa del front |
| Despliegue cloud | Render (blueprint `backend_fastapi/render.yaml`) + Vercel (fronts) | disco `/var/data` 10 GB, `autoDeploy` desde GitHub |
| CI | GitHub Actions `docker-build.yml` | build de `worker.Dockerfile` → Docker Hub `mfboggio/clipsai-worker:v28/:latest` en push a `dev` |
| Contratos | Paquete `backend/core` (Pydantic + ABCs) | handoff tipado track A ↔ track B |
| Front compartido | npm workspaces + `frontend_common/` | types/services/landing/estilos single-source; shims de 1 línea en ambos fronts |
| Estilos | Tailwind + `spark.css` Cyber-Tech Dark | `#0B0F17` bg, `#080C14` sidebar, `#121824` card, `#B4F105` lime glow |
| Otros | `requests`, `python-dotenv`, `anthropic`, `swagger-ui-express` | OAuth YouTube/Instagram/TikTok |

---

## 4. Estructura del repositorio

### 4.1 Árbol completo (sin `node_modules`, `dist`, `__pycache__`)

```
.
├── SISTEMA.md                   # ← ESTE documento maestro
├── ISSUES.md                    # backlog vivo (Issues 1–42, estado GitHub)
├── ENGINE_USO.md                # guía firma procesar_video + errores + CLI
├── docs/EVALUACION.md           # evaluación automática de calidad (cátedra, 6 Nov 2026)
│
├── .env                         # variables reales (gitignored) — ver .env.example
├── .env.example                 # plantilla (key con placeholder; la key real quedó en git history, ver §15)
├── docker-compose.yml           # 6 servicios: db, 2 backends, 2 frontends, ngrok
├── worker.Dockerfile            # imagen del worker RunPod GPU (§18) — CI → Docker Hub
├── start-dev.ps1                # orquestación híbrida/docker (-Docker, -Down, -Logs)
├── package.json / package-lock.json   # npm workspaces: frontend_common/react/vue
├── .github/workflows/docker-build.yml # build+push mfboggio/clipsai-worker en push a dev
│
├── init-scripts/
│   ├── 01-init-schema.sql       # DDL: usuarios, videos, jobs, clips + triggers + índices
│   ├── 02-social-accounts.sql   # DDL: social_accounts (OAuth) — Issue 22
│   └── README.md
│
├── backend/                     # Paquete desacoplado (contratos + tracks paralelos)
│   ├── README.md                # guía de tracks A/B
│   ├── handler.py               # handler RunPod serverless (§18) — procesa jobs entrantes
│   ├── RUNPOD.md                # guía de despliegue del worker + env vars de timeout
│   ├── Dockerfile               # via alternativa del worker (base mfboggio/clipsai-worker)
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
│   ├── render.yaml              # blueprint Render (Issue 47): disco /var/data + env RunPod/R2
│   ├── runpod_worker.py         # entrypoint del worker: runpod.serverless.start(handler)
│   ├── docker-sitecustomize.py  # reenvía backend_fastapi.* → app.* (paridad determinista)
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # app + lifespan (ALTER TABLE + storage_cleanup) + CORS + routers + /health
│       ├── config.py            # Settings (DATABASE_URL auto host, JWT, OAuth, LLM keys)
│       ├── database.py deps.py
│       ├── models/              # usuario, video, job, clip, social_account
│       ├── schemas/             # usuario, video, job, clip, stats, metrics, token
│       ├── security/            # hashing.py (bcrypt nativo), jwt.py (HS256)
│       ├── routers/             # auth, videos, jobs, clips, export, metrics, stats,
│       │                        # users, publish, subtitles, social_auth, sample
│       ├── services/            # engine, ass_generator, ffmpeg_service, hook_service,
│       │                        # whisper_service, publish_service, tiktok|youtube|instagram_service,
│       │                        # claude_service, llm_service, runpod_service, s3/boto3,
│       │                        # editor (9:16), storage_cleanup, social_common, transcript_utils
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
│       ├── hooks/useJobPolling.ts (2s) + usePublishSSE.ts + useIntegrations.ts
│       ├── components/          # Layout, Sidebar, Navbar, Avatar, ProfileMenu, Footer,
│       │                        # ProtectedRoute, ExportDropdown + subcarpetas auth/,
│       │                        # clip-library/, dashboard/, job-status/, upload/,
│       │                        # integrations/, landing/, legal/, settings/, navbar/
│       ├── pages/               # AuthPage, UploadPage, JobStatusPage, DashboardPage,
│       │                        # ClipLibraryPage, SettingsPage, IntegrationsPage,
│       │                        # LandingPage, legal/{Privacy,Terms,DataDeletion}Page
│       ├── styles/spark.css + landing.css + legal.css  # shims → frontend_common/styles
│       └── types/api.ts         # shim → frontend_common/types/api
│
├── frontend_vue/                # Frontend #2 (paridad 1:1)
│   ├── vite.config.ts (port 5173) / package.json
│   └── src/
│       ├── main.ts App.vue router/index.ts (guards + VITE_ALLOW_ANONYMOUS)
│       ├── stores/auth.ts       # Pinia
│       ├── api/client.ts (axios + interceptors) + api/services.ts
│       ├── composables/          # useJobPolling, usePublishStream, useIntegrations, useClipLibrary
│       ├── components/          # Layout, Sidebar, Navbar, Avatar, ExportDropdown, Footer
│       │                        # + subcarpetas auth/, clip-library/, dashboard/, job-status/,
│       │                        # upload/, integrations/, landing/, legal/
│       ├── views/               # Auth, Upload, JobStatus, Dashboard, ClipLibrary,
│       │                        # Settings, Integrations, Landing, legal/*, NotFound
│       ├── assets/spark.css     # shims → frontend_common/styles
│       └── types/api.ts         # shim → frontend_common/types/api
│
├── main.py                      # Pipeline monolítico (~1004L): LLM, prompt viral (1–5 clips), validar, cortar
├── audio_analyzer.py            # 372L: librosa RMS + eventos + KMeans → audio.json / momentos_virales.json
├── whisper_transcriber.py       # faster-whisper large-v3-turbo + parseo YouTube + GPU vía RUNPOD_GPU
├── video_processor.py           # 316L: clips verticales 9:16 + ASS palabra-por-palabra + hook (worker)
├── editor_viral.py              # 204L: reframe 9:16 crop-primero 1080x1920 + loudnorm (CLI)
├── engine.py                    # wrapper estable procesar_video → ProcesamientoResultado
├── engine_subprocess.py         # 183L: wrapper subprocess timeout 600s
├── ejemplo_engine.py            # ejemplo de invocación
├── limpiar.py                   # borra artefactos temporales
├── ENGINE_USO.md                # documentación del wrapper
│
├── frontend_common/             # paquete npm compartido por ambos fronts (workspaces)
│   ├── index.ts                 # re-exporta types, services/shared, helpers, landingData, landingSeo
│   ├── types/api.ts             # tipos API (+ RunPodProcessedClip, RunPodProcessResponse)
│   ├── services/shared.ts       # uploadFileToSignedUrl, triggerBlobDownload, normalizeVideo/Job, buildClipListQuery
│   ├── components/              # clip-library/helpers, landing/landingData, landing/landingSeo
│   ├── styles/                  # spark.css, landing.css, legal.css (single source of truth)
│   └── public/                  # favicon, og-clipsai.png, robots.txt, sitemap.xml
│
├── storage/                     # clips renderizados + uploads + sample_test.mp4
├── gaming_procesado/            # salida de ejemplo (audio.json, momentos_virales.json, clips/)
├── scripts/                     # _verify-common.sh (helpers), verify-auth/db/issue4/issue5.sh,
│                                # test_hooks.py, test_subtitles.py, make_og_image.py
├── tests/                       # fixtures
├── docs/EVALUACION.md           # evaluación automática de calidad (cátedra, 6 Nov 2026)
├── docs/design-reference.md     # tokens spark-admin
├── .github/CODEOWNERS + workflows/docker-build.yml   # CI del worker → Docker Hub
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
| Procesamiento serverless (RunPod) | `worker.Dockerfile` + `backend/handler.py` + `backend_fastapi/app/services/runpod_service.py` + `backend_express/src/services/runpod.ts` (§18) |
| Subida directa a R2 / presign | `backend_express/src/services/s3.ts` (SigV4 manual) · FastAPI `app/routers/videos.py` (boto3) |
| Render 9:16 en el worker | `video_processor.py` (`process_clip_vertical`) + `backend_fastapi/app/services/editor.py` |
| Limpieza de storage | `backend_fastapi/app/services/storage_cleanup.py` |
| Frontend compartido | `frontend_common/` (npm workspaces) |
| CI del worker | `.github/workflows/docker-build.yml` |
| Evaluación de calidad | `docs/EVALUACION.md` |
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

- `whisper_transcriber.py`: `parsear_transcripcion_youtube` + `transcribir_video`; fuerza GPU si `RUNPOD_GPU` ∈ {1,true,yes} con fallback a CPU.
- `editor_viral.py`: reframe 9:16 **crop-primero** con ffprobe + filtro `crop,scale` a 1080×1920 (sin OpenCV), `libx264 -crf 18`, 30 fps; CLI individual o por carpeta (`clips/` → `clips_editados/`).
- `video_processor.py`: usado por el worker RunPod — `generate_ass_from_segments()` + `process_clip_vertical()` por clip (9:16 + ASS + hook). El hook se emite como **primer evento ASS con estilo "Hook"** (el ffmpeg estático no tiene libfreetype, por lo que no se puede usar `drawtext`).
- `limpiar.py`: borra audio.mp3/.wav, audio.json, momentos_virales, clips/, __pycache__.

### 6.4 Cambios recientes del motor (oct–nov 2026)

- **FIX CRÍTICO (11-nov, PR #105): `run_clip_engine` tenía el pipeline local inalcanzable.**
  Tras el bloque de RunPod, `_native_segments` + Claude + el `return` final estaban anidados
  DENTRO de `_parse_transcript_native` después de su `return` (artefacto de merge): sin RunPod
  configurado, la función devolvía `None` y **todo job local terminaba en "0 clips → FAILED"**.
  El bloque se re-anidó dentro de `run_clip_engine`; verificado con introspección + tests
  (`test_engine_coverage.py`). Cubierto en 7 escenarios por `test_engine_coverage.py`.
- **Limitación conocida del modo local con `.txt`:** el fallback a transcripción de texto plano
  produce segmentos SIN timestamps de palabra → `build_sentence_map` (Claude) los exige y el
  pipeline falla con "Error en API de Claude: No hay timestamps...". Las subidas con solo `.txt`
  no producen clips en modo local — decisión de diseño pendiente (documentado en tests).
- **Prompt con recuento obligatorio:** `construir_prompt()` en `main.py` exige "**array con entre 1 y 5 clips… NUNCA `[]`**"; si el LLM devuelve vacío hay fallback determinístico. Los 6 criterios de viralidad mantienen pesos (revelación 10 → predicción 5) y duración obligatoria 30–90 s (óptimo 45–70).
- **Validación:** `validar_clips()` filtra duración fuera de 30–90 y `score < 5`, ordena desc y trunca a 10 (el log de error aún dice "15-120" — texto desactualizado).
- **Reframe robusto:** `backend_fastapi/app/services/editor.py` pasó a *crop-primero* para evitar frames intermedios de ~3413 px que provocaban OOM en Render; captura `returncode` de ffmpeg.
- **Normalización de segmentos:** `ass_generator` y `jobs.py` normalizan `start/end` de la transcripción con fallbacks; `ENABLE_ASS_HOOK` se inicializa defensivo (evita `UnboundLocalError` en `_run_job`).

### 6.5 Modos de ejecución: local vs RunPod (resumen)

| | Local (default) | RunPod serverless (§18) |
|---|---|---|
| Trigger | `POST /videos/{id}/jobs` → `BackgroundTasks _run_job` | `POST /api/videos/process` o delegación desde `run_clip_engine()` / `transcribe_video()` si `RUNPOD_API_KEY`+`RUNPOD_ENDPOINT_ID` tienen valor |
| Dónde corre | ffmpeg + Whisper + LLM en el backend | worker GPU (`worker.Dockerfile`, CUDA 12.1, Whisper en GPU) |
| Salida | `storage/clips/{job_id}/*.mp4` local | R2 `clips/{video_id}/{idx}_vertical.mp4` → `https://videos.clipsai.xyz/...` |
| Backend | renderiza ASS+hook en FastAPI | solo registra el resultado (`result_metadata._source="runpod_r2"`, `tags._render="runpod_r2"`) |
| Express | `spawnSync(python engine.py)` con timeout 20 s — **no** delega a RunPod | — |

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

**Integración actual:** `backend_fastapi/app/main.py` importa condicionalmente `backend.api.routes.retrim` y `stream`. Antes eso hacía que la superficie dependiera del layout (60 rutas en Docker vs 62 desde la raíz); **desde Issue 35 bis es determinista**: la imagen copia `backend/` y `docker-sitecustomize.py` (como `sitecustomize.py`) reenvía `backend_fastapi.*` → `app.*` reutilizando los mismos módulos. Resultado: **62 rutas en ambos layouts**, incluidas `POST /clips/{clip_id}/retrim` y `GET /jobs/{job_id}/stream`. Pendiente: que ambos backends importen `backend.core.schemas` en vez de sus schemas duplicados.

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

## 9. Backend Express (espejo — paridad 1:1 verificada)

**Estructura:** `src/app.ts` (cors, mounts, Swagger) + `src/db/index.ts` (pg.Pool, normaliza `postgresql+psycopg2://`) + `src/middleware/auth.ts` (jwt.verify HS256, mensajes "Token expirado/inválido") + `src/docs/swagger.ts` (OpenAPI 3.0, Issue 30) + `src/services/s3.ts` (presign SigV4 manual, sin aws-sdk) + `src/services/runpod.ts` (polling `/runsync`) + `src/routes/subtitles.ts`, `src/routes/socialAuth.ts`, `src/routes/apiVideos.ts`.

| Ruta | Implementación |
|------|----------------|
| `POST /auth/registro` `201/409` | bcryptjs truncate72 |
| `POST /auth/login`, `/auth/login/form` | HS256 60/1440min |
| `GET /auth/me` | authMiddleware |
| `POST /login`, `POST /registro` (raíz) | `compatAuthRouter` — alias de `_compat_auth` |
| `POST /videos` (multer diskStorage, mp4/mov/avi + txt/srt, 500MB) `201` | `routes/videos.ts` |
| `GET /videos` | lista usuario |
| `POST /videos/sample` | video de muestra (`SAMPLE_VIDEO_PATH`) → `runJob` |
| `POST /videos/:videoId/jobs` `202` | `setImmediate(runJob)` + `spawnSync python engine.py --json` (selección de proveedor por env) |
| `GET /jobs/:jobId` | status + metadata |
| `GET /clips` (`q, min_score, sort_by, page, limit, video_id, status`) | `SORT_MAP`, `ILIKE` |
| `GET/PATCH/DELETE /clips/:clipId` | ownership (404 antes de validar body, como FastAPI) |
| `GET /clips/:clipId/descarga` | FileResponse / dummy |
| `POST /clips/:clipId/re-render` | re-render ASS/Hook (necesita ffmpeg) |
| `POST /clips/:clipId/retrim` | re-corte FFmpeg a nuevo rango 5–90s (router opcional de `backend/api/routes/retrim.py`) |
| `GET /jobs/:jobId/stream` | SSE progreso del job (router opcional de `backend/api/routes/stream.py`) |
| `POST/GET /clips/:clipId/subtitles` (+ `/status`) | pipeline ASS + fallback a `videos.transcript` |
| `POST /clips/:clipId/publicar` + `/publish` `202` | `runPublish()` 2s → `PUBLISHED` o webhook real |
| `GET /clips/:clipId/publish-stream` | SSE publicación (EventSource vía `?token=`) |
| `POST /api/videos/upload-url` | presign R2 (`services/s3.ts`, verificado 404 NoSuchKey) |
| `POST /api/videos/process` | RunPod `/runsync` + `services/runpod.ts` |
| `GET /auth/social/status` + `/accounts`, `DELETE /{platform}`, `{youtube,instagram,tiktok}/{connect,callback}` | `routes/socialAuth.ts` (9 endpoints OAuth2) |
| `GET /clips/export`, `/jobs/:jobId/export` (+ `/api/v1` alias) | csv/json |
| `GET /metrics`, `/api/metrics` | cálculo idéntico FastAPI |
| `GET /stats/summary` | idem |
| `GET/PUT /users/me`, alias `GET/PUT/PATCH /me`, `POST /users/me/change-password` + `/me/change-password`, `PUT /me/password` (también con prefijo `/api`) | bcryptjs |
| `GET /docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`, `/api-docs`, `/api-docs.json` | swagger-ui-express + spec OpenAPI 3.0 (Issue 30) |
| `GET /health` | `{status:ok}` |

**Divergencias:** ninguna en la superficie de API. El montaje en `/api` de `usersRouter` replica los dos prefijos de `include_router` (`''` y `'/api'`), por lo que existen `/users/me` y `/api/users/me` (y sus alias `/me`). Único superset deliberado: `/api-docs` y `/api-docs.json` (criterio de aceptación de Issue 14). Mismo `TOKEN` funciona en `:8000` y `:3001` (misma DB + mismo `JWT_SECRET`).

**Divergencias de comportamiento (no de superficie) — pendientes de alinear:**
- **Jobs:** FastAPI delega en RunPod cuando está configurado (o renderiza local con ASS+hook); Express hace `spawnSync('python', [engine.py, ...])` **local** con timeout de 20 s y sin render ASS+hook ni fallback. Un job largo puede fallar en Express y pasar en FastAPI.
- **Publicación:** Express implementa `runPublish()` (2 s → `PUBLISHED` o webhook real) mientras FastAPI hace el upload OAuth real; verificar equivalencia por plataforma.
- **Subida a R2:** ambos exponen `/api/videos/upload-url` + `/api/videos/process`, pero solo FastAPI conecta el flujo completo con `jobs`.

**Verificación (comandos):**
```bash
cd backend_express
npm run typecheck              # tsc --noEmit
npm run audit:openapi          # 58 rutas montadas = 58 documentadas
npm run audit:parity           # FastAPI 62 ≈ Express 64 (paridad 1:1, 0 diferencias)
```

`scripts/audit-parity.mjs` compara el inventario real de FastAPI (`scripts/fastapi-routes.json`,
snapshot autoritativo) contra las rutas que Express monta en `app.ts` + `routes/*.ts`. Regenerar el
snapshot con la imagen ya construida (que incluye `backend/` y el alias `backend_fastapi.*` →
`app.*`):
```
docker compose build backend_fastapi
docker compose run --rm --no-deps -T backend_fastapi python -c "..." > backend_express/scripts/fastapi-routes.json
```

**Manejo de errores (estandarizado, Issue 35):** `lib/apiClient.ts` (React) y `api/client.ts`
(Vue) comparten la misma política de fallo de sesión: `/jobs/*` reintento silencioso, rutas
`/me` sin destruir sesión, cualquier otro fallo de sesión → limpiar token + `/login`. Acepta
**401 y 403 "Not authenticated"** porque FastAPI responde 403 al faltar el header (OAuth2) y
Express 401.

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

**Rutas (ambos):** `/` landing pública (Issue 32, sin auth; con sesión activa redirige a `/dashboard`), `/politica-de-privacidad` + `/terminos-y-condiciones` + `/eliminacion-de-datos` páginas legales (Issue 33, públicas), `/auth`, `/login→/auth`, `/dashboard`, `/clips`, `/library` (Vue; React alias borrado a `/dashboard`), `/upload`, `/jobs/:jobId`, `/settings`, `/dashboard/integrations`, `/settings/integrations`, `/404` (Vue), `*→/dashboard` (React).

### 10.2 Páginas clave

- **Auth:** tabs Login/Registro, `full_name` opcional, showPassword, alerts 401/409/422, JWT en localStorage, rehidrata en F5.
- **Upload:** `max-w-3xl`, 2 dropzones `dropzone-neon` (dashed lime glow), video `.mp4/.mov/.avi` + transcript `.txt/.srt` → `POST /videos 201` → `POST /jobs 202` → `/jobs/:id`.
- **JobStatus:** polling 2s; badges PENDING ámbar, PROCESSING sky spinner, COMPLETED verde + cards (`titulo`, inicio-fin mono, `score-badge-neon`, transcript preview), FAILED rojo con `error_message`.
- **Dashboard:** KPIs `total_jobs, total_clips, time_saved_hours, avg_score`; recharts `BarChart` (React) vs barras CSS (Vue); `platform/score_distribution`; `recent_activity[7]`; empty CTA.
- **Biblioteca:** toolbar 1 fila (`flex p-3 bg-[#121824] rounded-xl`, 56px): search debounce 350ms → `?q=`, `min_score/sort_by`, toggle grid/list, paginación `page/limit 10`; modal Publicar (platform + caption 500 + `webhook_override_url`) → badge `PUBLISHING` amber pulse → `PUBLISHED` emerald + link `social_post_url`; `ExportDropdown` csv/json; delete confirm.
- **Integraciones:** `IntegrationsPage`/`IntegrationsView` + `settings/IntegrationsSettings` — conectar/desconectar YouTube/Instagram/TikTok vía `/auth/social/*/connect`, badge `Conectado` + `Ver post` (Issue 28).
- **Settings:** avatar 56px, `PUT /users/me`, change-password, preferencias theme/export_format.
- **Layout:** Sidebar `#080C14` fixed 280px (80px minimized con fix `dropdown-menu-profile` fixed left 88px), Navbar sticky con búsqueda → `/clips?q=`, Footer, `ProtectedRoute`.
- **Landing (Issue 32):** `LandingPage.tsx` / `LandingView.vue` en `/` — hero con CTA `Probar gratis → /auth`, "Cómo funciona" con 3 tabs interactivos (cargar → análisis IA → publicación), "Sobre nosotros" (motor IA, análisis de audio, scoring de viralidad), features grid (9:16, subtítulos ASS, autopublicación) y footer con enlaces legales (`/politica-de-privacidad`, `/terminos-y-condiciones`, `/eliminacion-de-datos`). SEO: `index.html` con title/description/canonical/og/twitter + `robots.txt` + `sitemap.xml` + `og-clipsai.png`. Lighthouse SEO 100/100.
- **Legales (Issue 33):** `pages/legal/` + `views/legal/` — `PrivacyPage`/`PrivacyView` (`/politica-de-privacidad`), `TermsPage`/`TermsView` (`/terminos-y-condiciones`), `DataDeletionPage`/`DataDeletionView` (`/eliminacion-de-datos`). Layout compartido `LegalLayout` + `legal.css`. Contenido: datos recopilados, uso, compartidos, seguridad, derechos, contacto, plazo de eliminación (30 días), revocación OAuth.
- **Video de muestra (Issue 34):** `POST /videos/sample` (router `sample.py`) — crea job con video de muestra sin subir archivo. Botón "Probar con video de muestra" en `UploadPage`/`UploadView`. Video en `backend_fastapi/storage/sample/sample.mp4` (configurable vía `SAMPLE_VIDEO_PATH`).

### 10.3 Deuda conocida en UI

- ~~Duplicados `LibraryPage`/`LibraryView`~~ — eliminados en Issue 35.
- ~~`axios` muerto en React~~ — desinstalado (Issue 35); en Vue sí está en uso.
- `frontend_common` **no está declarado como dependencia en React** (depende del hoisting de npm workspaces) y no hay alias en `vite.config.ts`: la resolución depende de `node_modules`. En Docker los fronts montan solo `./frontend_*` e instalan sin workspaces → **riesgo de fallo de resolución de `frontend_common` dentro de los contenedores** (ver §18.6).
- Pendiente declarado en Issue 42: consolidar fixtures (`backend/tests/fixtures/` ↔ `tests/fixtures/`) y helpers internos de `clips.ts`.

### 10.4 `frontend_common/` — paquete compartido (npm workspaces)

- Raíz `package.json` declara `"workspaces": ["frontend_common","frontend_react","frontend_vue"]`; Vue lo lista como dependencia (`"frontend_common": "*"`) y ambos resuelven vía `tsconfig` `paths: {"frontend_common/*": ["../frontend_common/*"]}`.
- Contenido: `types/api.ts` (tipos de la API, incl. `RunPodProcessedClip`/`RunPodProcessResponse`), `services/shared.ts` (`uploadFileToSignedUrl`, `triggerBlobDownload`, `normalizeVideo`, `normalizeJob`, `buildClipListQuery`), helpers de clip-library, `landingData`/`landingSeo`, los 3 CSS (`spark`, `landing`, `legal`) y `public/` (favicon, OG image, robots, sitemap) — **single source of truth**: los archivos en cada frontend son shims de 1 línea (`export * from 'frontend_common/...'` / `@import url('frontend_common/styles/...')`).
- `publicDir: '../frontend_common/public'` en ambos `vite.config.ts`.

### 10.5 Subida directa a R2 y tiempo real

- **Subida directa (Issue de calidad 2026):** `DirectUploadPanel` (React) / equivalente Vue — `POST /api/videos/upload-url` → PUT presignado a R2 → `POST /api/videos/process`. Sin `multipart` al backend; el archivo nunca pasa por el server web.
- **SSE de publicación:** `frontend_react/src/hooks/usePublishSSE.ts` (usado en `ClipLibraryPage`) y `frontend_vue/src/composables/usePublishStream.ts` consumen `GET /clips/{id}/publish-stream` → el badge cambia `PUBLISHING → PUBLISHED` con URL del post sin recargar (base de la Issue 31).

---

## 11. Tema y diseño Cyber-Tech Dark

`spark.css` unificado en ambos frontends (`frontend_react/src/styles/` y `frontend_vue/src/assets/`), derivado de la plantilla Spark Admin (tokens ya extraídos en `docs/design-reference.md`).

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

### 12.5 Flujo serverless (RunPod + R2)

```bash
# 1) Presign de subida directa (el archivo no pasa por el backend)
curl -X POST http://localhost:8000/api/videos/upload-url -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"file_name":"river.mp4","file_type":"video/mp4"}'
# 2) PUT del archivo a la upload_url devuelta (R2)
# 3) Disparar procesamiento (RunPod runsync; requiere RUNPOD_* + AWS_* en .env)
curl -X POST http://localhost:8000/api/videos/process -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_key":"uploads/<uuid>.mp4","transcription_text":"00:00 - Hola...","video_id":"<uuid>"}'
# 4) Los clips quedan en https://videos.clipsai.xyz/clips/<video_id>/N_vertical.mp4
#    y el job en la DB con result_metadata._source = "runpod_r2"
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
ANTHROPIC_API_KEY=...          # placeholder — la key real quedó en git history, ver §15
ANTHROPIC_MODEL=claude-sonnet-4-20250514   # .env.example: claude-sonnet-5; main.py default: claude-sonnet-5
ANTHROPIC_VERSION=2023-06-01
OPENAI_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
DEEPSEEK_API_KEY=
API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
MODEL=deepseek-chat

# RunPod Serverless + Cloudflare R2 (§18) — solo se delega si RUNPOD_API_KEY y RUNPOD_ENDPOINT_ID tienen valor
RUNPOD_API_KEY=
RUNPOD_ENDPOINT_ID=
RUNPOD_API_BASE_URL=https://api.runpod.ai     # opcional (default)
RUNPOD_REQUEST_TIMEOUT_SECONDS=95             # por request al endpoint
RUNPOD_TIMEOUT_SECONDS=1800                   # timeout total del job
RUNPOD_POLL_INTERVAL_SECONDS=2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_ENDPOINT_URL=                             # endpoint S3 de Cloudflare R2
AWS_REGION=auto
BUCKET_NAME=clipsai-videos
R2_PUBLIC_URL=https://videos.clipsai.xyz      # dominio público del bucket (default en el worker)
RUNPOD_GPU=1                                  # fuerza Whisper a CUDA en el worker

# Storage / despliegue
STORAGE_DIR=/var/data                         # o STORAGE_PATH; default /var/data (disco Render)
STORAGE_CLIPS_DIR=/var/data/clips
UPLOAD_DIR=/var/data/uploads
SAMPLE_VIDEO_PATH=                            # video de muestra (Issue 34)

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

**Notas:**
- El **worker RunPod no corre en compose**: su imagen se construye en CI (`.github/workflows/docker-build.yml`, contexto raíz + `worker.Dockerfile`) y se publica en Docker Hub (`mfboggio/clipsai-worker:v28`/`:latest`); RunPod la levanta serverless bajo demanda.
- `backend_fastapi` se builda con **contexto raíz** (el Dockerfile necesita `backend/` para `api/routes/{retrim,stream}.py` y el `docker-sitecustomize.py`).
- El worker comparte `./storage` con los backends en dev, pero en producción la comunicación es vía R2 (no vía volumen).
- **Despliegue en la nube (Issue 47):** `backend_fastapi/render.yaml` es un blueprint de Render (web service + Postgres managed + disco 10 GB en `/var/data`); las secrets se cargan con `sync: false` desde el dashboard. Fronts en Vercel.
- `start-dev.ps1`: `-Docker` (todo compose), default (híbrido: `docker compose up -d db backend_fastapi backend_express` + frontends locales con `concurrently` + ngrok), `-Down`, `-Logs`. Scripts npm raíz equivalentes: `dev`, `dev:full`, `dev:docker`, `dev:ngrok`, `install:all`.

---

## 15. Seguridad

**Implementado:**
- bcrypt nativo truncate 72 bytes (evita bug passlib+bcrypt4) en FastAPI; `bcryptjs` en Express.
- JWT HS256 con `type: access` y expiración; `HTTPBearer` 401; distinción `ExpiredSignatureError` vs `JWTError`.
- CORS con allowlist + regex dominios; `redirect_slashes=False` evita 307 abiertos.
- Sin secretos en código de routers/services (leen `os.environ` / `Settings`).
- Usuario no-root en Dockerfile FastAPI; límite 500MB en uploads; extensiones permitidas whitelist.

**Deuda abierta (Issue 13 / 21):**
- ⚠️ **`ANTHROPIC_API_KEY` real en `git history`** — el `.env.example` actual ya usa placeholders, pero la key sigue en el historial: requiere rotación + `git filter-repo`/`BFG` + limpieza `git grep sk-ant`.
- `JWT_SECRET` con default `dev_secret...` en `config.py` (mitigado por `min_length=16`, pero debe obligarse en prod).
- Sin `express-rate-limit` / `slowapi`.
- Sin TLS en `pg.Pool` (solo local/bridge).
- `.env` trackeado históricamente (verificar `git ls-files .env`).
- **SSRF en el flujo serverless:** `backend/handler.py` descarga `video_url`/`transcription_url` arbitrarios — verificar que use `backend/core/security/ssrf_guard.py` (ver §18.6.6).

---

## 16. Scripts, utilidades y testing

| Script | Uso |
|--------|-----|
| `scripts/_verify-common.sh` | helpers compartidos (`log/pass/fatal`, `http_request`, `register_or_login`…) que sourcean los `verify-*.sh` |
| `scripts/verify-auth.sh` | curl registro/login/me |
| `scripts/verify-db.sh` | `psql \dt` + `\d` de las tablas |
| `scripts/verify-issue4.sh` | POST /videos + polling jobs |
| `scripts/verify-issue5.sh` | CRUD clips |
| `scripts/test_hooks.py`, `scripts/test_subtitles.py` | pruebas de hook y subtítulos |
| `scripts/make_og_image.py` | genera `public/og-clipsai.png` (1200×630) para ambos frontends |
| `backend_express/scripts/audit-openapi.mjs` | rutas montadas = rutas documentadas (`npm run audit:openapi`) |
| `backend_express/scripts/audit-parity.mjs` | FastAPI ↔ Express ruta por ruta contra `fastapi-routes.json` (`npm run audit:parity`) |
| `limpiar.py` | limpia artefactos del motor |
| `start-dev.ps1` | orquestación del stack |
| `.github/workflows/docker-build.yml` | CI: build+push de `worker.Dockerfile` a Docker Hub en push a `dev` |

**Validación:**
- Typecheck frontends: `npm run typecheck` (React `tsc --noEmit`, Vue `vue-tsc --noEmit`).
- Build: `npm run build` → `dist/`.
- Express: `npm run typecheck`, `curl /health`, `curl /docs`.
- **Paridad backends (Issue 6):** `cd backend_express && npm run audit:openapi && npm run audit:parity` (el script ya compila en Windows vía `pathToFileURL`).
- Infra: `docker compose logs -f`, `docker compose ps`, `curl :8000/health`, `curl :8000/docs`.
- Pipeline Issue 29: `test_issue_29_pipeline.py` (ffprobe 9:16, ASS PlayRes, fallback).
- Landing Issue 32: `npm run build` + `npx lighthouse http://localhost:3000/ --only-categories=seo` (SEO 100/100) + `curl /robots.txt` + `curl /sitemap.xml`.
- Duplicación: `npx jscpd --min-lines 5 --min-tokens 50` (ver Issue 42 en `ISSUES.md`).
- **No hay CI que ejecute tests/typecheck/lint** (el único workflow es el build del worker); la evaluación de calidad se corre manual/externamente vía `docs/EVALUACION.md`.

**Suite de tests Python (Fase 1 + Fase 2, 395 tests herméticos — sin DB, sin red, sin FFmpeg):**

| Suite | Cubre |
|---|---|
| `backend_fastapi/tests/conftest.py` + `_fixtures.py` | harness: `FakeSession` (protocolo SQLAlchemy de los routers), factories de modelos con `__name__` del modelo (para `db.get`), `TestClient` con overrides, `DATABASE_URL=""` forzado |
| `test_routers_coverage.py` (87) | routers: auth/JWT real, users, videos (presign R2), jobs, clips, export, metrics, stats, social OAuth mockeado, sample, SSE |
| `test_services_coverage.py` (44) | security JWT/bcrypt, `transcript_utils`, `ass_generator`, `storage_cleanup`, `runpod_service`, `hook_service`, `ffmpeg_service` |
| `test_jobs_heavy_coverage.py` (33) | `_run_job` completo (R2/local/FAILED/Claude), `run_job_safely`, helpers |
| `test_publish_service_coverage.py` (34) | `publish_clip_task` + publicadores TikTok/IG/YouTube con HTTP mockeado, refresh de tokens |
| `test_social_editors_coverage.py` (32) | conectores OAuth (tiktok/youtube/instagram), `editor.py` (reframe), `claude_service` |
| `test_engine_coverage.py` (29) | motor: timestamps/ventana de hook, WAV, `run_clip_engine` (RunPod + local+Claude) |
| `test_pipeline_heavy_coverage.py` (36) | `whisper_service` (SDK mockeado) + `subtitle_pipeline` completo |
| `backend/tests/test_runpod_integration.py` (12) | handler RunPod + cliente + presign |
| `backend/tests/test_tracks_core_coverage.py` (63) | stubs del paquete desacoplado, `core/security` (ssrf/vault/rate-limit/storage), handler ramas |

Comandos de cobertura (desde la raíz):
```bash
python -m pytest -q -p no:cacheprovider --cov=app --cov=backend --cov=backend_fastapi.app --cov-report=term   # global agregada (69%)
python -m pytest -q -p no:cacheprovider --cov=app --cov=backend_fastapi/app --cov-report=term-missing        # literal (64%)
```
Reglas de oro de la suite: mockear SIEMPRE `is_runpod_configured` en tests "locales" (el `.env`
real de la máquina tiene RUNPOD_API_KEY y delegaría de verdad); fechas de test en UTC (los
routers agrupan por UTC); `caplog.at_level(...)` para capturar INFO; no usar
`Mock(side_effect=Mock)` (devuelve Mock hijo sin atributos — usar función → `SimpleNamespace`).

---

## 17. Estado de Issues, calidad y roadmap

Fuentes: [`ISSUES.md`](./ISSUES.md) (backlog detallado) y [`docs/EVALUACION.md`](./docs/EVALUACION.md) (evaluación automática de la cátedra, generada 6 Nov 2026 sobre `main`).

### 17.1 Resumen ejecutivo de issues

| Estado | Cantidad | Lista |
|--------|----------|-------|
| ✅ Completado | 27 | 1, 2, 3, 4, 5, 6, 7, 14, 17, 18, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35 (+ 35 bis) (+ PR #34 Spark) **+ Fase 1 y Fase 2 de calidad (PR #104 mergeado / #105 abierto)** |
| ⚠️ Parcial | 2 | 13 (seguridad/compose), 42 (dedup: jscpd en 6.53%, pendientes declarados) |
| ⏳ Pendiente / a cerrar | 2 | 31 (SSE publish — **implementado en código**, falta cierre en GitHub #51), 47 (despliegue Render — blueprint creado) |
| ↩️ Cerradas vía otras | 3 | 8, 9, 10/11/12 → Issues 27/28/29 |

### 17.2 Estado por área

| Área | Estado | Detalle |
|------|--------|---------|
| Infra DB + Docker | ✅ | Postgres 15 + volumen + healthcheck + DDL idempotente + 6 servicios compose |
| Motor IA | ✅ | `main.py` + wrapper `engine.py` + `engine_subprocess.py` + prompt 1–5 clips |
| FastAPI | ✅ | ~78 operaciones, auth, videos/jobs/clips, publish, subtitles, social, export, metrics, docs, sample, retrim/stream |
| Express | ✅ 100% superficie | paridad 1:1 verificada (`npm run audit:parity`); **divergencias de comportamiento** en jobs/publicación (ver §9) |
| React / Vue | ✅ ~95% | auth, upload (dropzone + subida directa R2), jobs, dashboard, biblioteca con SSE, settings, integraciones, landing, legales |
| Subtítulos + Hook | ✅ | Issue 29 — `ENABLE_ASS_HOOK=True` en `jobs`; en worker vía `video_processor.py` |
| OAuth + Publish real | ✅ | Issues 22–28 — YouTube/Instagram/TikTok + SSE de estado en UI |
| Docs OpenAPI | ✅ | FastAPI `/docs` + Express `/docs`, `/openapi.json`, `/redoc` |
| **Serverless RunPod + R2** | ✅ funcional / publicado en `main` | pipeline completo (mergeado con la Fase 1, PR #104); worker v28 en Docker Hub — verificar alineación `dev`↔`main` |
| Despliegue cloud | ⚠️ | blueprint Render creado (Issue 47); ngrok legacy + Cloudflare Tunnel para callbacks |
| Seguridad | ⚠️ | key filtrada histórica (Issue 13), rate-limit ausente, `JWT_SECRET` con default dev |
| Calidad (cátedra) | ⚠️ mejorando | índice cátedra 5/100 (informe 6-nov desactualizado); DBG 0 ✅, Coh ✅, cobertura 69 % — Fase 3 para 80 % |
| CI | ⚠️ | solo build del worker; sin workflow de tests/typecheck |

### 17.3 Evaluación de calidad (docs/EVALUACION.md — 6 Nov 2026, perfil exigente)

> ⚠️ **El informe de la cátedra quedó desactualizado tras la Fase 1 y Fase 2** (se genera
> externamente sobre `main`; su próximo recálculo ya verá: DBG 0, Coh resuelto,
> `backend_express/dist` fuera del rastreo y ~395 tests). Estado REAL al 11-nov:

| Métrica | Cátedra (6-nov) | Estado real (11-nov) |
|---|---|---|
| DBG (console.log/print) | 24 ❌ | **0** en los 4 archivos reportados ✅ |
| Cohesión baja | 1 (`editor_viral.py`) ❌ | **resuelto** (geometría/render/catálogo/fachada) ✅ |
| Cobertura de tests | 18,0 % ❌ | **69 % agregada** (suite 395 tests; core app+backend: 88 %) — meta 80 % → Fase 3 |
| Duplicación | 10,3 % ✅ | sin cambios (jscpd 6,53 %) ✅ |
| Secretos/SQL/any/HTTP | 0 ✅ | sin cambios ✅ |
| Complejidad alta | 273 bloques ❌ | sin cambios (Fase 3+) ❌ |
| Índice de calidad | 5/100 ❌ | a recalcular por la cátedra (DBG/Coh/Cob ya atienden las 3 señales más pesadas) |

**Autoría (RepoSense, 6-nov):** mateo 64 commits · 66 % LOC · IC 79 — SantiValla 39 commits · 34 % LOC · IC 50.

**Brecha restante para el índice ≥50:** complejidad (273 bloques) y cobertura (80 %: Fase 3 —
restos de `jobs.py` 382, `publish_service` 314, `main.py` lifespan 104, `runpod_service` 89).

### 17.4 Estado de ramas y sincronización

- **Fase 1 de calidad MERGEADA a `main`** (PR **#104**, merge `35289e9`; rama `fix/quality-audit-score` borrada por GitHub tras el merge). Incluye: DBG 0, refactor `editor_viral.py`, fix de `publish_service.py` (sintaxis rota), fix alias `/registro`, fix `audit-openapi.mjs` Windows, 330 tests, `ISSUES_CALIDAD_PENDIENTES.md`.
- **Fase 2 en PR ABIERTO #105** (`feat/quality-perfection-phase2` → `main`): fix crítico de código inalcanzable en `engine.py`, 65 tests nuevos (395 total), cobertura 69%, `dist/` fuera del rastreo, 2 flakes de reloj corregidos.
- ⚠️ El pipeline RunPod+R2 ahora **está en `origin/main`** (venía con el merge de #104, que había arrancado desde `fix/sync-main-with-dev`).
- ⚠️ Riesgo vigente: la imagen del worker en Docker Hub (v28) se builda desde `dev`; verificar que `dev` esté alineado con `main` post-merge.

### 17.5 Issues pendientes y deuda abierta

| # | Título | Estado / criterio |
|---|--------|-------------------|
| — | **Fase 3 de cobertura** | restos de `jobs.py` (382), `publish_service.py` (314), `main.py` lifespan (104), `runpod_service` polling (89) → para superar 80% agregada (ver `ISSUES_CALIDAD_PENDIENTES.md` issue 3) |
| 13 | Seguridad | rotar `ANTHROPIC_API_KEY` filtrada + `git filter-repo`/BFG; obligar `JWT_SECRET` en prod; rate-limit |
| 42 | Deduplicación profunda | jscpd 6,53 % ✅; pendientes: unificar `app/services` ↔ `backend_fastapi/app/services` (~700 L), fixtures duplicados, helpers `clips.ts`, gemelos `backend/services/*` ↔ `backend/track_*/*` |
| 31 | SSE estado de publicación en UI | implementado (`usePublishSSE` / `usePublishStream` → `/clips/{id}/publish-stream`); **falta cerrar en GitHub #51** |
| 47 | Despliegue Render | blueprint creado; falta validar end-to-end (OAuth callbacks con dominio público, disco, RunPod secrets) |
| — | Cache de Meta en publicación | `_get_ngrok_domain` + `_resolve_instagram_business_id` hacen HTTP en cada publish (ver `ISSUES_CALIDAD_PENDIENTES.md` issue 1) |
| — | Fallback `.txt` sin timestamps | `engine.py` local con transcripción de texto plano no puede generar clips (build_sentence_map exige timestamps de palabra) — decisión de diseño pendiente |
| — | Paridad de comportamiento Express | jobs: `spawnSync` local 20 s sin ASS+hook ni RunPod (§9) |
| — | CI de calidad | no hay workflow que ejecute tests/typecheck/audit en PR |

### 17.6 Próximos pasos recomendados (insumo para decisión)

Prioridad sugerida, en función de impacto × esfuerzo:

1. **Sincronizar el código con `origin/main` (ALTA, bajo esfuerzo).** Sin esto, nada de lo demás es verificable en producción ni por la cátedra. Incluye PR de `fix/sync-main-with-dev` y verificar que Render/Docker Hub construyan del mismo commit.
2. **Subir la calidad medible (ALTA, esfuerzo medio) — ataca el índice 5/100:**
   - Eliminar los 24 `print`/`console.log` (rápido: mueve el índice a zona segura de DBG).
   - Sumar tests de camino principal y errores (cobertura 18 % → objetivo incremental 40–50 % primero; el 80 % es ambicioso para el cierre).
   - Refactor puntual de complejidad en los archivos con más señales (`jobs.py`, `handler.py`, `main.py`, `clips.ts`).
   - Cerrar Issue 13 (rotación de key + limpieza de historial).
3. **Cerrar el ciclo RunPod+R2 (ALTA, esfuerzo medio):** documentar y probar E2E el flujo directo (upload presign → process → clips en R2), alinear Express (hoy no delega a RunPod y tiene timeout de 20 s) o explícitamente degradarlo a "solo FastAPI", y agregar `R2_PUBLIC_URL` a `.env.example`.
4. **CI en PRs (MEDIA):** workflow con `typecheck` + `audit:parity` + `pytest` + build de fronts; además evitar pushes directos a `main` (6 detectados).
5. **Funcionalidad nueva (MEDIA, según objetivos del producto):** multi-idioma i18n, roles admin/editor, paginación cursor para 10k+ clips, índice GIN sobre `tags`, analytics de retención por clip, editor timeline (fuera de alcance actual — requiere decisión de scope).

---

## 18. Procesamiento serverless (RunPod + R2), despliegue y CI

### 18.1 Worker en RunPod Serverless (GPU)

| Archivo | Rol |
|---|---|
| `worker.Dockerfile` (raíz) | imagen del worker: base `pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime`, fuentes DejaVu + fontconfig (verificadas con `fc-list` — sin ellas los subtítulos salen invisibles), ffmpeg **estático** johnvansickle con check `libx264`, `backend_fastapi/requirements.txt`, cuDNN/CUDA registrados con `ldconfig`, copia `engine.py`, `main.py`, `whisper_transcriber.py`, `audio_analyzer.py`, `video_processor.py`, `backend/`, `runpod_worker.py` → `CMD ["python","-u","runpod_worker.py"]` |
| `backend_fastapi/runpod_worker.py` | `runpod.serverless.start({"handler": handler})` |
| `backend/handler.py` (~323 L) | handler real: descarga video (≤500 MB) y transcripción (≤10 MB) → `engine.procesar_video` → `video_processor.process_clip_vertical()` por clip (9:16 + ASS + hook) → sube a R2 → responde JSON |
| `backend/RUNPOD.md` | guía de despliegue + env vars de timeout |
| `backend/Dockerfile` | vía alternativa (base `mfboggio/clipsai-worker:v3`) |

**Contrato del job:** input `{"input": {video_url, transcription_url | transcription_text, video_id}}` → output `{status:"COMPLETED", video_id, engine:"clipsai_native", clips:[{index, url_r2, titulo, hook_texto, score, inicio, fin, duracion, criterio_principal, primer_segundo, motivo}], clip_count, transcription_segments}`.

**Env del worker:** `AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY/ENDPOINT_URL/REGION`, `BUCKET_NAME` (default `clipsai-videos`), `R2_PUBLIC_URL` (default `https://videos.clipsai.xyz`), `RUNPOD_GPU` (fuerza CUDA en Whisper), `HUGGINGFACE_HUB_CACHE`, `PROJECT_ROOT`.

**Protocolo:** `POST {RUNPOD_API_BASE_URL}/{endpointId}/runsync` + polling `GET .../status/{jobId}` — timeout total 1800 s, request 95 s, poll 2 s; errores → 502 (o 504 por timeout). Imagen publicada por CI: `mfboggio/clipsai-worker:v28` / `:latest`.

### 18.2 Puntos de integración en los backends

| Backend | Cliente | Endpoints / hooks |
|---|---|---|
| Express | `src/services/runpod.ts` (port 1:1 del Python) | `POST /api/videos/upload-url`, `POST /api/videos/process` (`routes/apiVideos.ts`) |
| FastAPI | `app/services/runpod_service.py` | `POST /api/videos/upload-url` (`videos.py:64`), `POST /api/videos/process` (`videos.py:91`) |
| FastAPI (delegación indirecta) | `services/engine.py:345-368` → `run_clip_engine()`; `services/whisper_service.py:283` → `transcribe_video()` | llamados desde `routers/jobs.py:_run_job` y `tasks/subtitle_pipeline.py` |

**Comportamiento:** si `RUNPOD_API_KEY` y `RUNPOD_ENDPOINT_ID` tienen valor → delega; si no → procesamiento local. Cuando el worker devuelve clips con `url_r2`, FastAPI marca el job `COMPLETED` al 100 % **sin render local** (`result_metadata._source="runpod_r2"`, `tags._render="runpod_r2"`, `tags.has_ass=true` — commit `9a0e409`).

⚠️ **Express no delega en jobs**: `routes/jobs.ts` hace `spawnSync('python', [engine.py, ...])` local con timeout 20 s. Ver divergencias §9.

### 18.3 Cloudflare R2 y subida directa

- **`backend_express/src/services/s3.ts`**: presign **SigV4 manual sin aws-sdk** (canonical request, `UNSIGNED-PAYLOAD`, path-style `<endpoint>/<bucket>/<key>` que R2 acepta). FastAPI usa `boto3`.
- **Flujo:** 1) `POST /api/videos/upload-url {file_name, file_type}` → `{upload_url (PUT presign 900 s), file_key: uploads/{uuid}{ext}`; 2) el front sube con `uploadFileToSignedUrl()` (PUT directo, **el archivo no pasa por el backend**); 3) `POST /api/videos/process` con exactamente uno de `file_key` (GET presign 3600 s) o `video_url`, más `transcription_url` o `transcription_text` + `video_id` → dispara RunPod.
- **Consumidores:** `frontend_common/services/shared.ts`, `DirectUploadPanel.tsx`, `services/api.ts` (React) y `api/services.ts` (Vue).
- **Dominio público:** las URLs `*.r2.cloudflarestorage.com` son privadas (403); se usa `R2_PUBLIC_URL` o el default `https://videos.clipsai.xyz` (commit `42a5574`).
- ⚠️ `R2_PUBLIC_URL` **no está en `.env.example`** (el worker usa el default).

### 18.4 Storage, Render y limpieza

- `backend_fastapi/app/services/storage_cleanup.py` (164 L): `cleanup_storage()` en el `lifespan`, `ensure_disk_space(min_free_mb=500)` antes de cada upload y en el `finally` de cada job. Env: `STORAGE_DIR`/`STORAGE_PATH` (default `/var/data`).
- **`backend_fastapi/render.yaml`** (Issue 47): web service en Render (plan starter, `autoDeploy`, health `/health`), disco persistente 10 GB montado en `/var/data`, Postgres managed, y todas las secrets RunPod/R2/LLM/OAuth con `sync: false` (se cargan en el dashboard).
- Fronts desplegados en Vercel (`FRONTEND_URL=https://api.clipsai.xyz` en `.env.example` apunta al backend público).

### 18.5 CI (GitHub Actions)

- **Único workflow:** `.github/workflows/docker-build.yml` — trigger `workflow_dispatch` + push a `dev`; buildx + push a Docker Hub (`DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`) de `worker.Dockerfile` con tags `mfboggio/clipsai-worker:v28` y `:latest`, cache GHA.
- Historial de tags: v21 (21 oct) → v28 (5 nov).
- `main.yml` fue **eliminado** (`aef4e75`) porque pisaba `:latest`.
- **No hay CI de tests/typecheck/lint/audits** — gap relevante (ver §17.5).

### 18.6 Gaps y riesgos conocidos del flujo serverless

1. **Sincronización de código:** el pipeline RunPod+R2 está 59 commits adelante de `origin/main` (§17.4); Render despliega `origin/main` y el worker se builda desde `dev`.
2. **`frontend_common` en Docker:** los contenedores de fronts montan solo `./frontend_*` e instalan sin npm workspaces → los shims `export * from 'frontend_common/...'` pueden no resolver (falta `npm install` en raíz o alias en Vite/Docker).
3. **Express fuera del flujo serverless** (spawnSync local, timeout 20 s, sin ASS+hook).
4. **`R2_PUBLIC_URL` sin documentar** en `.env.example`.
5. **Costos/escalabilidad:** RunPod cobra por GPU activa; no hay mecanismo de cola ni reintentos visibles en la UI si el job serverless falla (el front ve el job de la DB).
6. **Seguridad del flujo:** los `video_url`/`transcription_url` que recibe el handler deben validarse contra SSRF (existe `backend/core/security/ssrf_guard.py` — verificar que esté cableado en `handler.py`).

---

## 19. Plantilla para nuevas Issues

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
> **Documentos relacionados:** [`ISSUES.md`](./ISSUES.md) · [`ENGINE_USO.md`](./ENGINE_USO.md) · [`docs/EVALUACION.md`](./docs/EVALUACION.md) · `backend/README.md` · `backend/RUNPOD.md` · `docs/design-reference.md` · `init-scripts/README.md`
