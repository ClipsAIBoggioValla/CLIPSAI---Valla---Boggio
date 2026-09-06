# ClipsAI — Plataforma SaaS de Generación Automática de Clips Virales

> Convierte videos largos (podcast, streaming, entrevistas) en clips verticales 1080x1920 listos para TikTok/Reels/Shorts con scoring de viralidad IA, subtítulos quemados y hook inicial. Sistema multi-stack: **dual-backend (FastAPI + Express)**, **dual-frontend (React + Vue 3)**, **PostgreSQL + Worker asíncrono + Motor Python (Whisper + librosa + Claude/DeepSeek + FFmpeg)**.

```
Video (.mp4/.mov/.avi) + Transcripción (.txt/.srt) → Job asíncrono (pending→processing→completed|failed) → clips[] {titulo, inicio/fin, score, preview} → biblioteca + dashboard + export
```

---

## Índice
1. [Visión y Arquitectura](#1-visión-y-arquitectura)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Estructura del Repositorio — Todas las Carpetas y Archivos](#3-estructura-del-repositorio)
4. [Modelo de Datos y Base de Datos](#4-modelo-de-datos)
5. [Motor de IA (Python)](#5-motor-de-ia)
6. [Backend FastAPI (Referencia)](#6-backend-fastapi)
7. [Backend Express (Paridad)](#7-backend-express)
8. [Frontends React / Vue](#8-frontends)
9. [Tema y Diseño Cyber-Tech Dark](#9-tema-y-diseño)
10. [Variables de Entorno](#10-variables-de-entorno)
11. [Guía de Instalación y Comandos](#11-guía-de-instalación)
12. [Flujo de Prueba End-to-End](#12-flujo-de-prueba)
13. [API — Resumen de Endpoints](#13-api-endpoints)
14. [Scripts y Utilidades](#14-scripts)
15. [Testing y Validación](#15-testing)
16. [Roadmap e Issues](#16-roadmap)
17. [Licencia](#17-licencia)

---

## 1. Visión y Arquitectura

### Objetivo
Automatizar el trabajo de un editor de clips virales: detectar momentos con mayor potencial de retención/viralidad combinando **análisis de audio** (energía, cambios bruscos, clustering) + **LLM sobre transcripción** y recortar automáticamente con FFmpeg.

Fuera de alcance a propósito: streams en vivo, multi-cámara podcast/gaming, edición manual timeline, traducción multi-idioma, móvil nativo.

### Diagrama de despliegue
```
                 ┌─────────────────────┐
  React :3000 ───┤                     ├──────┐
  (fetch)        │                     │      ▼
                 │   FastAPI :8000     │   PostgreSQL :5432
  Vue :3000/5173 ┤   /auth /videos     │   (volumen postgres_data)
  (axios)        │   /jobs /clips      │      ▲
                 │   /stats /metrics   │      │
                 │   /docs (Swagger)   │      │
                 └─────────┬───────────┘      │
                           │ BackgroundTasks │
                           ▼                 │
                 ┌──────────────────┐        │
                 │ Worker Engine    │────────┘
                 │ audio + IA +     │
                 │ FFmpeg (simulado │
                 │  o real)         │
                 └──────────────────┘

  Express :3001 (paridad parcial) ─► misma DB ─► mismos JWT
```

- **Persistencia:** PostgreSQL 15 Alpine dockerizada, healthcheck `pg_isready`, init-scripts idempotentes.
- **Asincronía:** `BackgroundTasks` por defecto (sin Redis). Migrable a Celery+Redis si `REDIS_URL` existe.
- **Dual stack:** ambos backends y ambos frontends consumen el **mismo contrato HTTP** y la **misma DB/JWT**.

---

## 2. Stack Tecnológico

| Capa | Tecnología | Versión / Notas |
|------|------------|-----------------|
| **Orquestación** | Docker + Docker Compose v2 | `postgres:15-alpine`, healthchecks, network `clipsai-net` |
| **DB** | PostgreSQL 15 | `uuid-ossp`, triggers `updated_at`, CHECK constraints |
| **Backend #1** | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 (sync) + Pydantic 2 + python-jose + bcrypt + uvicorn | `redirect_slashes=False`, CORS + OPTIONS handler, lifespan migrations |
| **Backend #2** | Node + Express 4.19 + pg 8.11 + jsonwebtoken + bcryptjs + tsx + TypeScript 5.5 | `type:module`, pool con normalización `DATABASE_URL` |
| **Frontend #1** | React 18.3 + TypeScript 5.5 + react-router-dom 6 + Context + Tailwind 3.4 + Vite 5.3 + recharts | `fetch` apiClient, `useJobPolling` 2000ms |
| **Frontend #2** | Vue 3.4 + TypeScript 5.5 + vue-router 4 + Pinia 2 + Axios + Tailwind 3.4 + Vite 5.3 | `axios` client + interceptors, `useJobPolling` composable |
| **Motor IA** | Python + librosa + faster-whisper (large-v3-turbo) + scikit-learn KMeans + Anthropic Claude / DeepSeek / OpenAI + FFmpeg | pipeline `extraer_audio → analizar → formatear → enriquecer → LLM → validar → cortar` |
| **Estilos** | Tailwind + spark.css (tokens Cyber-Tech Dark) + bootstrap-icons | Dark `#0B0F17`, sidebar `#080C14`, cards `#121824`, lime `#B4F105` |
| **Template** | spark-admin-1.0.0 | referencia visual, no import directo |

---

## 3. Estructura del Repositorio

### 3.1 Árbol completo (sin `node_modules`, `dist`, `__pycache__`)
```
.
├── .env                        # variables reales (gitignored) — ver .env.example
├── .env.example                # plantilla con POSTGRES_*, JWT_*, ANTHROPIC_*, etc.
├── .gitignore / .gitattributes
├── docker-compose.yml          # db + backend_fastapi (Express/frontends pendientes Issue 13)
├── package-lock.json            # lockfile raíz (frontend_react)
│
├── init-scripts/
│   ├── 01-init-schema.sql      # DDL idempotente: usuarios, videos, jobs, clips + triggers + índices
│   └── README.md               # cómo re-ejecutar (down -v)
│
├── backend_fastapi/            # Backend de referencia (completo)
│   ├── Dockerfile              # python:3.11-slim, curl, non-root appuser, uvicorn :8000
│   ├── requirements.txt        # fastapi, uvicorn, sqlalchemy, psycopg2-binary, pydantic*, passlib, python-jose, etc.
│   ├── .dockerignore
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI app, lifespan (ALTER TABLE IF NOT EXISTS), CORS, health, routers
│       ├── config.py           # Settings pydantic-settings (DATABASE_URL, JWT_SECRET 16+ chars, etc.)
│       ├── database.py         # create_engine + SessionLocal + get_db()
│       ├── deps.py             # HTTPBearer + get_current_user (decode JWT, validar UUID)
│       ├── models/             # SQLAlchemy ORM
│       │   ├── usuario.py      # tabla usuarios (UUID, email unique, hashed_password, avatar_url, theme)
│       │   ├── video.py        # videos (usuario_id FK, file_path, transcript, duration_seconds)
│       │   ├── job.py          # jobs (video_id FK, status enum pending/processing/completed/failed, result_metadata JSONB)
│       │   └── clip.py         # clips (job_id FK, video_id, title, file_path, start/end FLOAT, score, tags JSONB, status, publication_status)
│       ├── schemas/            # Pydantic v2
│       │   ├── usuario.py      # UsuarioCreate/Login/Read, UserResponse, UserUpdate, PasswordChange
│       │   ├── video.py        # VideoResponse (id, filename, created_at)
│       │   ├── job.py          # JobResponse (status UPPER + serializer)
│       │   ├── clip.py         # ClipResponse, ClipListItem, ClipListResponse (paginado)
│       │   ├── stats.py        # StatsSummaryResponse
│       │   ├── metrics.py      # MetricsResponse (7 días)
│       │   └── token.py        # Token + TokenPayload
│       ├── security/
│       │   ├── hashing.py      # bcrypt nativo (truncate 72 bytes, hashpw/checkpw)
│       │   └── jwt.py          # create_access_token / decode_access_token (HS256, exp 60min, type=access)
│       ├── services/
│       │   └── engine.py       # run_clip_engine() — wrapper simulado (sleep + clips dummy) o real si main.py disponible
│       └── routers/
│           ├── auth.py         # POST /auth/registro 201/409, POST /auth/login (JSON+form), GET /auth/me
│           ├── videos.py       # POST /videos (multipart video+transcription, valida ext/tamaño 500MB), GET /videos
│           ├── jobs.py         # POST /videos/{id}/jobs 202 + BackgroundTasks _run_job, GET /jobs/{id}
│           ├── clips.py        # GET /clips (q, min_score, sort_by, page, limit, video_id, status), GET/PATCH/DELETE /clips/{id}, GET /clips/{id}/descarga (FileResponse + dummy)
│           ├── export.py       # GET /jobs/{id}/export?format=csv|json, GET /clips/export
│           ├── metrics.py      # GET /metrics + /api/metrics (7 días jobs/clips/minutes, platform_distribution)
│           ├── stats.py        # GET /stats/summary (total_videos/clips, avg_score, score_distribution, time_saved, recent_job)
│           └── users.py        # GET/PUT/PATCH /users/me + /me + /api/users/me, POST /users/me/change-password
│
├── backend_express/            # Backend espejo (paridad parcial ~35%)
│   ├── package.json / tsconfig.json
│   ├── src/
│   │   ├── index.ts            # bootstrap (listen)
│   │   ├── app.ts              # express + cors (3000/3001/5173), mounts /health, /clips, /metrics, /stats, /users (+/api/users)
│   │   ├── db/index.ts         # pg.Pool, buildConnectionString (normaliza postgresql+psycopg2://)
│   │   ├── middleware/auth.ts  # jwt.verify HS256, req.user.id, mensajes Token expirado/inválido
│   │   └── routes/
│   │       ├── clips.ts        # GET /clips (q, min_score, sort_by, page, limit) — faltan video_id/status y CRUD :id
│   │       ├── export.ts       # GET /clips/export, /jobs/:id/export (valida UUID, csv/json)
│   │       ├── metrics.ts      # GET /metrics (cálculo idéntico FastAPI)
│   │       ├── stats.ts        # GET /stats/summary (idéntico)
│   │       └── users.ts        # GET/PUT/PATCH /me + change-password (bcryptjs truncate72, valida email/theme)
│   └── dist/                   # build compilado (tsc)
│
├── frontend_react/             # Frontend #1 (React 18)
│   ├── package.json / vite.config.ts (port 3000, alias @, proxy /api→:8000) / tailwind.config.js / tsconfig.json
│   ├── index.html / .env / .env.example (VITE_API_URL=http://localhost:8000)
│   ├── public/index.html
│   └── src/
│       ├── main.tsx            # StrictMode + BrowserRouter + AuthProvider + App
│       ├── App.tsx             # Router: /auth, /login→/auth, ProtectedLayout → /dashboard, /clips, /upload, /jobs/:jobId, /settings, *→/dashboard
│       ├── index.css / styles/spark.css  # tokens Cyber-Tech Dark (ver §9)
│       ├── types/api.ts        # User*, AuthToken, Video*, Job {status UPPER, result_metadata.clips}, Clip*, Stats, Metrics, ApiError, ClipListParams
│       ├── lib/apiClient.ts    # fetch wrapper: BASE_URL, Bearer auto, parseError 401/409/422, http.get/post/patch/delete
│       ├── services/api.ts     # authService, videoService, jobService, clipService, statsService, metricsService, exportService + normalize
│       ├── context/AuthContext.tsx # login/register/logout, persist localStorage clipsai_token, init() con /auth/me
│       ├── hooks/
│       │   ├── useJobPolling.ts      # polling 2000ms, clearInterval en COMPLETED/FAILED, refresh()
│       │   └── useUploadAndProcess.ts # flujo idle→uploading→creating_job→polling (no usado, UploadPage usa lógica manual)
│       ├── components/
│       │   ├── Layout.tsx      # Sidebar + Navbar + Outlet + Footer, minimized/mobileOpen → body.sidebar-minimized
│       │   ├── Sidebar.tsx     # brand, Menu (Dashboard/Biblioteca/Subir), Páginas (Ajustes), profile dropdown (z-50 fixed si colapsado)
│       │   ├── Navbar.tsx      # btn desktop toggle, crear dropdown, búsqueda 350ms debounce → /clips?q=, fullscreen, notifs
│       │   ├── Avatar.tsx      # iniciales + gradient lime→emerald (bg-gradient-to-tr from-emerald-500 to-[#B4F105] text-[#080C14])
│       │   ├── ProfileMenu.tsx # dropdown up/down, fixed si sidebar-minimized (left 88px bottom 20px z-9999)
│       │   ├── Footer.tsx      # © clipsai + links
│       │   ├── ProtectedRoute.tsx
│       │   └── ExportDropdown.tsx # csv/json con Content-Disposition parsing + triggerBlobDownload
│       └── pages/
│           ├── AuthPage.tsx          # tabs Login/Registro, alerts 401/409/422, showPassword, full_name opcional
│           ├── UploadPage.tsx        # dropzone neon dashed lime, file inputs video+txt, videoService.upload → jobService.createJob → /jobs/:id
│           ├── JobStatusPage.tsx     # StatusBadge PENDING/PROCESSING/COMPLETED/FAILED, result_metadata.clips cards, modo simulado
│           ├── DashboardPage.tsx     # recharts BarChart, KPIs (jobs, clips, time_saved, avg_score), platform/score distribution, recent 7d, empty CTA
│           ├── ClipLibraryPage.tsx   # toolbar compacta 1 fila (ver §9), grid clip-card hover neon + score-badge-neon, list table-custom, paginación
│           ├── LibraryPage.tsx       # duplicado idéntico de ClipLibraryPage (ruta /library y /clips)
│           └── SettingsPage.tsx      # editar perfil (PUT /users/me), cambiar password, preferencias theme/export_format + Avatar 56px
│
├── frontend_vue/               # Frontend #2 (Vue 3) — paridad ~95% con React
│   ├── package.json / vite.config.ts (port 3000, plugin vue, alias @, sin proxy) / tailwind.config.js / tsconfig.json
│   ├── index.html / .env / .env.example
│   ├── env.d.ts
│   └── src/
│       ├── main.ts             # createApp + Pinia + router + authStore.init()
│       ├── App.vue             # <RouterView/>
│       ├── assets/spark.css / main.css # idéntico a React
│       ├── types/api.ts        # 1:1 con React
│       ├── api/client.ts       # axios baseURL, interceptors Bearer, 401 → removeItem + router.push /login
│       ├── api/services.ts     # auth/video/job/clip/stats/metrics/export (paridad, responseType blob)
│       ├── services/api.ts     # re-export de api/services + client
│       ├── stores/auth.ts      # Pinia useAuthStore (user, token, isAuthenticated, init/login/register/logout)
│       ├── composables/useJobPolling.ts # ref+watch, getter jobId ()=>string, 2000ms, auto-clean
│       ├── router/index.ts     # /, /auth, /dashboard, /clips, /library, /upload, /jobs/:jobId, /settings, /404, beforeEach guard (requiresAuth)
│       ├── components/         # Layout.vue, Sidebar.vue, Navbar.vue, Footer.vue, Avatar.vue, ExportDropdown.vue (1:1 React)
│       └── views/              # AuthView.vue, UploadView.vue, JobStatusView.vue, DashboardView.vue (barras CSS, no recharts), ClipLibraryView.vue, LibraryView.vue, SettingsView.vue, NotFoundView.vue
│
├── main.py                     # Pipeline monolítico 957 líneas: cargar_env, ANTHROPIC_*/OPENAI_*, verificar_ffmpeg, extraer_audio, analizar_audio_video, formatear_transcripcion, preparar_transcripcion_para_ia, enriquecer_datos_para_ia, construir_prompt (experto viral rioplatense, 6 criterios pesados, reglas 30-90s), _post_con_retry, llamar_claude/openai, obtener_clips_ia, timestamp helpers, reparar_json, validar_clips (filtro 30-90s, score≥5, top10), cortar_clip (ffmpeg libx264 ultrafast crf18), procesar_clips, main() CLI (modos manual/whisper/single)
├── audio_analyzer.py           # 372L: librosa load, calcular_rms, detectar_eventos (grito, silencio, cambio_brusco), detectar_momentos_intensos, cambios_escena (onset), limpiar_eventos, normalizar 0-10, clustering KMeans 10 (StandardScaler + timestamp/intensidad/tipo), analizar_audio → audio.json + momentos_virales.json
├── whisper_transcriber.py      # 261L: parsear_transcripcion_youtube (regex RE_TS HH:MM:SS - Texto), transcribir_video (faster-whisper large-v3-turbo-ct2, cuda/float16 else cpu/int8, vad_filter, beam 5, progress bar)
├── editor_viral.py             # 292L: VideoEditor (vertical 1080x1920 fps30, haarcascade face crop, sample cada 3s, loudnorm I=-16 TP=-1.5 LRA=11) — nota: "sin subtítulos" (Issue 10 pendiente)
├── engine.py                   # 378L Wrapper estable: procesar_video(video, transcripcion) → ProcesamientoResultado {exito, clips[], carpeta_salida, error, error_tipo, error_detalle}, dataclass ClipInfo, validación temprana, tempfile.mkdtemp clipsai_*, manejo granular Audio/Transcripcion/IA/Generacion, CLI --json/--no-cleanup
├── engine_subprocess.py        # 183L Wrapper subprocess: procesar_video_subprocess(..., timeout 600s) → subprocess.run [python engine.py --json] + parse JSON + TimeoutExpired
├── ejemplo_engine.py           # ejemplo invocación procesar_video con prints
├── whisper_words.json          # salida palabras Whisper
├── whisper_transcriber.py      # ver arriba
├── transcripcion_test.txt / test_audio.wav / audio_analyzer.py — fixtures de prueba
│
├── gaming_procesado/           # output de ejemplo de un video gaming (audio.json, momentos_virales.json, transcripcion_formatted.txt, clips/ vacío)
├── spark-admin-1.0.0/          # plantilla base (assets/css/main.css 3187L con tokens Plus Jakarta Sans, brand forest/lime, etc.) — no import directo, tokens replicados en spark.css
├── docs/
│   └── design-reference.md     # extracción tokens spark-admin (paleta, radios 24/18/14/10/6, sombras, cards/botones)
├── scripts/
│   ├── verify-auth.sh          # curl /auth/registro /login /me
│   ├── verify-db.sh            # psql \dt \d
│   ├── verify-issue4.sh        # POST /videos + polling GET /jobs
│   └── verify-issue5.sh        # GET /clips CRUD
├── limpiar.py                 # borra audio.mp3/.wav, audio.json, momentos_virales, clips/, __pycache__, *.pyc
├── ENGINE_USO.md               # guía firma procesar_video, ejemplos programático/API/CLI/subprocess, tabla error_tipo→HTTP, limpieza
├── PROYECTO.md                 # objetivo, límites in/out, alcances funcionales/no funcionales, objetivos medibles (issues)
├── ISSUES.md                   # 14 issues con dependencias, criterios y evidencias (este archivo actualizado extiende con estado real)
└── README.md                   # (este archivo)
```

---

## 4. Modelo de Datos

### 4.1 Esquema relacional (`init-scripts/01-init-schema.sql`)
```
usuarios 1──N videos 1──N jobs 1──N clips
```

| Tabla | Columnas clave | Constraints/Index |
|-------|----------------|-------------------|
| **usuarios** | `id UUID PK uuid_generate_v4()`, `email VARCHAR(255) UNIQUE NOT NULL`, `hashed_password VARCHAR(255) NOT NULL`, `full_name VARCHAR(100)`, `created_at/updated_at TIMESTAMPTZ` | trigger `set_updated_at()`, índice email |
| **videos** | `id UUID PK`, `usuario_id UUID FK CASCADE`, `original_filename VARCHAR(255) NOT NULL`, `file_path TEXT NOT NULL`, `duration_seconds FLOAT`, `transcript TEXT`, `created_at/updated_at` | FK `fk_videos_usuario`, índice `idx_videos_usuario_id` |
| **jobs** | `id UUID PK`, `video_id UUID FK CASCADE`, `status VARCHAR(50) DEFAULT pending`, `error_message TEXT`, `created_at/updated_at` | `chk_jobs_status IN (pending,processing,completed,failed)`, índice `idx_jobs_video_id` |
| **clips** | `id UUID PK`, `job_id UUID FK CASCADE`, `title VARCHAR(255)`, `file_path TEXT NOT NULL`, `start_time FLOAT NOT NULL`, `end_time FLOAT NOT NULL`, `social_network VARCHAR(50) NULL`, `publication_status VARCHAR(50) DEFAULT draft`, `published_at TIMESTAMPTZ`, `created_at/updated_at` | `chk_clips_time_range (end>start)`, `chk_clips_publication_status`, `chk_clips_social_network`, índice `idx_clips_job_id` |

**Evolución en runtime (lifespan FastAPI + lazy Express):** `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para `usuarios.avatar_url VARCHAR(500), theme_preference VARCHAR(20) DEFAULT 'dark'`, `videos.transcription_filepath, transcript TEXT, duration_seconds`, `jobs.result_metadata JSONB, error_message`, `clips.video_id UUID, score DOUBLE, tags JSONB, status VARCHAR DEFAULT 'ready'`, `updated_at`. Idempotente.

### 4.2 Entidades Pydantic / ORM
- **Usuario:** `UsuarioCreate {email, password 8-128, full_name?}`, `UsuarioRead {id, email, full_name, created_at, updated_at}`, `UserResponse {+avatar_url, theme_preference}`, `UserUpdate` alias `nombre↔full_name`.
- **Video:** `VideoResponse {id, filename, created_at}` (filename alias `original_filename`).
- **Job:** `JobResponse {id, video_id, status→UPPER, error_message, result_metadata {clips?: {titulo,inicio,fin,score,transcript_preview}[], video?, engine?}, created_at, updated_at}`.
- **Clip:** `ClipResponse/ClipListItem {id, job_id, title, score, start_time, end_time, transcript, created_at}`, `ClipUpdate {title?, tags?}`.
- **Stats/Metrics:** `StatsSummaryResponse {total_videos, total_clips, avg_score, estimated_time_saved_minutes=clips*15, score_distribution[0-40,41-70,71-100], recent_job}`, `MetricsResponse {total_jobs, total_clips, total_minutes_processed, time_saved_hours=minutes*3/60, platform_distribution, recent_activity[7]}`.

### 4.3 JWT
- `HS256`, `JWT_SECRET` min 16 chars, `JWT_EXPIRE_MINUTES=60`, payload `{sub: UUID, iat, exp, type:"access"}`, `Authorization: Bearer <token>`, `HTTPBearer(auto_error=True)` → 401. Login doble: `POST /auth/login` JSON y `POST /auth/login/form` OAuth2 (`username=email`) para Swagger Authorize.

---

## 5. Motor de IA

### 5.1 Pipeline (`main.py` + `engine.py`)
1. **Validación + FFmpeg check** (`_validar_entradas`, `ffmpeg -version`).
2. **Extraer audio** `ffmpeg -y -i video -q:a 0 -map a audio.mp3`.
3. **Analizar audio** (`audio_analyzer.analizar_audio`): RMS (frame 2048 hop 512) → eventos grito/silencio/cambio → momentos intensos (ventana 5) → onset scene changes → limpiar 2s → normalizar 0-10 → KMeans 10 clusters → `audio.json` + `momentos_virales.json`. Top 50 eventos sorted por intensidad.
4. **Formatear transcripción** `formatear_transcripcion`: regex `^(\d{1,2}:\d{2}(?::\d{2})?)` → limpia `… segundos/minutos …` → `HH:MM:SS - Texto` → `transcripcion_formatted.txt`.
5. **Preparar para IA** `preparar_transcripcion_para_ia`: si >150 segmentos, comprime por factor `total/150` concatenando textos.
6. **Enriquecer** `enriquecer_datos_para_ia`: correlaciona eventos audio↔transcripción por distancia <30s.
7. **Prompt + LLM** `construir_prompt`: experto viral TikTok rioplatense, 6 criterios pesados (revelación 10, controversia 9, dato 8, emocional 7, técnico 6, predicción 5) + señales audio (+1 si intensidad>7) + reglas inicio 3-4s antes, fin 3-4s después, 30-90s óptimo 45-70s, evita "y/pero" sin contexto, output JSON array max 10 score≥7. `_post_con_retry` sleep `2*intento`, `llamar_claude` (Anthropic x-api-key, max_tokens 8192, thinking disabled) o `llamar_openai_compatible` (Bearer, MODEL deepseek-chat). Parse tolerante `re.search r'\[[\s\S]*\]'` + `reparar_json`.
8. **Validar clips** `validar_clips`: filtra sin inicio/fin, duración 30-90s, score<5, sort score desc top10, formatea HH:MM:SS.
9. **Cortar** `cortar_clip` `ffmpeg -ss inicio -i video -t duracion -c:v libx264 preset ultrafast crf 18 -c:a aac -movflags +faststart` → `clips/clip_i.mp4` + `clips_info.json`.
10. **Wrapper** `engine.py:procesar_video` aísla en `tempfile.mkdtemp(prefix=clipsai_)`, captura granular `ValidacionError|DependenciaError|AudioError|TranscripcionError|PreparacionIAError|ConexionError|TimeoutError|IAError|GeneracionError|SinClipsValidos|ErrorInterno` con `traceback` → `ProcesamientoResultado.to_dict()` para JSON. `limpiar_directorio_trabajo()` borra `gettempdir()` path.

### 5.2 Audio Analyzer (`audio_analyzer.py`)
Dependencias `librosa`, `numpy`, `scikit-learn`. Funciones: `cargar_audio`, `calcular_rms`, `detectar_eventos`, `detectar_momentos_intensos`, `detectar_cambios_escena`, `limpiar_eventos`, `normalizar_intensidad`, `detectar_momentos_virales_clustering`.

### 5.3 Whisper (`whisper_transcriber.py`)
`faster-whisper large-v3-turbo-ct2`, device `cuda/float16` else `cpu/int8`, `vad_filter true`, `beam 5`, barra 40 chars con ETA. `parsear_transcripcion_youtube` para forzar `HH:MM:SS -`.

### 5.4 Editor Viral (`editor_viral.py`)
`VideoEditor(clips_dir, salida_dir)` 1080x1920 fps30, `haarcascade` face detection sample cada 3s → crop 9/16 centrado → scale ffmpeg, `loudnorm I=-16 TP=-1.5 LRA=11`. Actualmente **sin subtítulos quemados** ni hook reordering (ver Issues 10/11 pendientes).

### 5.5 Integración API
`backend_fastapi/app/services/engine.py:run_clip_engine` hoy **simulado**: sleep 0.5s + 2 clips dummy `00:00:10-00:00:55 score8`, `00:01:00-00:01:40 score7` (si `main` importable, 1 clip `00:01:00-00:01:45` engine:real). Debe wirearse a `engine.py:procesar_video` o `engine_subprocess` para producción.

---

## 6. Backend FastAPI

**App factory** `FastAPI(redirect_slashes=False)` + `lifespan` create_all + ALTERs + CHECK recreate + `CORSMiddleware` `allow_origins=[3000,3001,5173]` + `handle_options_preflight` 200.

**Routers montados:**
```
/auth/*           → auth.router
/videos           → videos.router (POST 201, GET)
/videos/{id}/jobs → jobs.router (POST 202)
/jobs/{id}        → jobs.router (GET)
/clips*           → clips.router
/jobs/{id}/export, /clips/export → export.router
/metrics, /api/metrics → metrics.router
/stats/summary     → stats.router
/users/me + /me + /api/users/me → users.router (doble mount)
```

**Detalles clave:**
- **Seguridad:** `hashing.py` bcrypt nativo truncate 72 bytes (evita bug passlib+bcrypt4), `jwt.py` python-jose con distinción ExpiredSignatureError vs JWTError.
- **Jobs background:** `_run_job(job_id)` crea `SessionLocal()` nueva, `status=processing`, `run_clip_engine`, normaliza `inicio/fin` HH:MM:SS→segundos, crea `Clip` con `storage_path=""`, guarda `result_metadata`, `completed/failed`.
- **Clips descarga:** `FileResponse` busca `storage_path/file_path` else `video.filepath` else dummy `/tmp/clip_{id}.txt`.
- **Export:** `csv.writer` header `ID,Título,Inicio,Fin,Score,Transcripción` o JSON `total_clips, clips[], avg_score`.
- **Requisitos:** ver `requirements.txt` (nota: falta `bcrypt` explícito y `python-dotenv`, `passlib` no usado).

---

## 7. Backend Express

**Estado actual:** paridad ~35%. Completo: `GET /health`, `GET /clips` (q, min_score, sort_by, page, limit), `GET /clips/export`, `GET /jobs/:id/export`, `GET /metrics|/api/metrics`, `GET /stats/summary`, `GET /users/me + /api/users/me`, `PUT/PATCH /me`, `POST /users/me/change-password`. **Faltante crítico:** `POST /auth/registro|login`, `POST/GET /videos`, `POST /videos/:id/jobs`, `GET /jobs/:id`, `GET/PATCH/DELETE /clips/:id`, `GET /clips/:id/descarga`.

**App:** `src/app.ts` cors + express.json, `src/db/index.ts` Pool con normalización URL, `src/middleware/auth.ts` jwt.verify HS256 con fallback `changeme` inseguro.

**Divergencias:** valida `email` con `includes('@')` vs EmailStr, no valida UUID en todos lados → 500 pg si mal formato (FastAPI 422), `SORT_MAP` idem, cálculo metrics `Math.round*100/100` idem.

**Pendiente Issue 6:** implementar auth/videos/jobs + `multer` + `runClipEngine` portado + `Dockerfile` + compose service.

---

## 8. Frontends

### 8.1 Paridad React ↔ Vue (95%)

| Capa | React | Vue | Notas |
|------|-------|-----|-------|
| Lenguaje | TS 5.5 strict | TS 5.5 vue-tsc | |
| Estado auth | `Context/AuthContext.tsx` + localStorage `clipsai_token` | `Pinia useAuthStore` | init() revalida `/auth/me` |
| HTTP | `fetch` (`lib/apiClient.ts`, `BASE_URL=VITE_API_URL||:8000`, Bearer auto, parseError 401/409/422) | `axios` (`api/client.ts`, baseURL, interceptors, 401→removeItem+push /login) | paridad funcional |
| Servicios | `services/api.ts` auth/video/job/clip/stats/metrics/export | `api/services.ts` + re-export | normalize `status.toUpperCase()`, `title/filename` |
| Router | `react-router-dom` ProtectedRoute/Layout | `vue-router` beforeEach guard | React `Navigate /auth`, Vue `/login→/auth` |
| Polling | `hooks/useJobPolling.ts` 2000ms | `composables/useJobPolling.ts` getter ()=>string | isTerminal COMPLETED/FAILED |
| Upload | `pages/UploadPage.tsx` manual | `views/UploadView.vue` Composition API | idem flujo dropzone neon |
| JobStatus | `JobStatusPage` StatusBadge + modo simulado cards | `JobStatusView` v-if | idem |
| Dashboard | `recharts` BarChart | barras CSS `div` | divergencia lib, mismos KPIs |
| Biblioteca | `ClipLibraryPage + LibraryPage` duplicado | `ClipLibraryView + LibraryView` duplicado | toolbar 1 fila (ver §9) |
| Build | `vite 5.3` `tsc -b && vite build` | `vite 5.3` `vue-tsc --noEmit && vite build` | |

**Router protegido:**
- React `/dashboard, /clips, /upload, /jobs/:jobId, /settings` dentro de `ProtectedLayout`; `/auth, /login→/auth` público.
- Vue idem + `/library` alias, `/404` NotFound.
- `VITE_API_URL=http://localhost:8000` en ambos `.env`.

### 8.2 Páginas clave
- **Auth:** tabs Login/Registro, `full_name` opcional, `showPassword`, mapeo 401/409/422, JWT localStorage, rehidrata en F5.
- **Upload:** `max-w-3xl`, header lime badge, 2 dropzones `dropzone-neon` dashed lime glow, file inputs `.mp4/.mov/.avi` + `.txt/.srt`, botón primario lime glow `Subir y procesar` → `POST /videos 201` → `POST /videos/{id}/jobs 202` → `navigate /jobs/:id` + progress `animate-pulse`.
- **JobStatus:** polling 2s, `PENDING` ámbar, `PROCESSING` sky spinner, `COMPLETED` verde + clips cards `titulo, inicio-fin mono, score-badge-neon, transcript_preview` + nota `Modo simulado`.
- **Dashboard:** KPIs `total_jobs, total_clips, time_saved_hours, avg_score`, charts `platform_distribution` o `score_distribution`, `recent_activity[7]` barras violeta/emerald/amber.
- **Biblioteca:** ver §9.1.1 toolbar 1 fila, filtros `q, min_score, sort_by, page, limit 10, viewMode grid|list`, cards `clip-card hover:border-[#B4F105] hover:bg-[#161E2E] shadow neon` + badges, table `table-card-custom`, pagination, `hasFilters` reset.
- **Settings:** avatar 56px, editar perfil `PUT /users/me`, seguridad `POST /users/me/change-password`, preferencias `theme light/dark/system + export_format` localStorage + `documentElement.classList`.
- **Layout:** `Sidebar` `#080C14 border-gray-800` fixed 280px (80px minimized), `Navbar` sticky `#080C14`, `Footer` + `Outlet`.

---

## 9. Tema y Diseño

**Cyber-Tech Dark (aplicado en último rediseño global React+Vue):**
- `spark.css` unificado (copiado a ambos frontends) — `:root` tokens `--bg-app:#0B0F17`, `--bg-sidebar:#080C14`, `--bg-card:#121824`, `--border-subtle:rgba(255,255,255,0.08)`, `--border-sidebar:#1f2937`, `--text-primary:#F1F5F9`, `--text-secondary:#94A3B8`, `--brand-lime:#B4F105`, `--brand-lime-glow:0 0 20px rgba(180,241,5,0.35)`.
- **Sidebar:** `width var(--sidebar-width) bg #080C14 border-r #1f2937`, link active `rgba(180,241,5,0.12) border rgba(180,241,5,0.2) shadow glow`, profile `bg #121824 border subtle hover lime`.
- **Navbar:** `bg #080C14 backdrop-blur 16px border-b #1f2937`, `btn-quick-action bg #B4F105 text #080C14 shadow glow`, `navbar-search-input bg #121824 border subtle focus lime`, `navbar-action-btn bg #121824 hover lime`.
- **Cards:** `card-spark bg #121824 border subtle shadow-md hover border 12%`, `clip-card::before gradient lime→emerald on hover`, `kpi-card` top-line lime.
- **Dropdowns:** `bg #121824 border subtle shadow-xl`, item hover `rgba(180,241,5,0.10) color lime`.
- **Forms:** `form-control-custom bg #0B0F17 border subtle focus lime glow`, `table-search-input`, `form-select-custom` dark.
- **Botones:** `btn-custom-primary bg #B4F105 text #080C14 glow hover translateY-1px`, `btn-custom-light bg #121824`.
- **Dropzone neon:** `dropzone-neon border 2px dashed rgba(180,241,5,0.35) bg rgba(180,241,5,0.04) hover rgba(180,241,5,0.65) shadow 32px + radial glow`, icon `dropzone-icon-neon 52px bg rgba(180,241,5,0.12)`.
- **Progress:** `progress bg rgba(255,255,255,0.06) h-8px, progress-bar linear lime→emerald shadow lime`.
- **Login:** `login-wrapper bg #0B0F17 radial gradients lime/emerald, login-card bg #121824 border subtle shadow-xl, login-input bg #0B0F17 focus lime, btn-login lime glow`.
- **Badges:** `score-badge-neon high/mid/low` (lime/amber/red translucent + border + glow), `badge-table success/pending/failed`.

### 9.1.1 Barra Biblioteca (última refactorización)
- **Contenedor:** `flex flex-col md:flex-row items-center justify-between gap-4 p-3 bg-[#121824] rounded-xl border border-white/10` `min-height 56px` (quita padding excesivo, 1 fila desktop).
- **Izquierda:** `relative flex-1 max-w-md w-full` + `<i class="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">` + `input w-full pl-9 pr-4 py-2 bg-[#0B0F17] border-white/10 rounded-lg text-sm text-white placeholder-gray-400 focus:border-[#B4F105]`.
- **Derecha:** `flex items-center gap-3 w-full md:w-auto justify-end` + selects `bg-[#0B0F17] text-xs border-white/10 rounded-lg px-3 py-2 hover:border-white/20` + toggle `py-1 px-1 bg-[#0B0F17] border-white/10 rounded-lg flex gap-1` botones `px-3 py-1.5 rounded-md text-xs font-bold` active `bg-[#B4F105] text-[#080C14] shadow lime`.
- Aplicado idéntico en `frontend_react/src/pages/ClipLibraryPage.tsx` (+ LibraryPage) y `frontend_vue/src/views/ClipLibraryView.vue` (+ LibraryView).

### Collapsed sidebar fix
- `sidebar-wrapper overflow:visible`, `.flex-grow-1 overflow-y:auto`, `body.sidebar-minimized .sidebar-wrapper 80px`, `body.sidebar-minimized .dropdown-menu-profile {position:fixed !important; left:88px !important; bottom:20px !important; z-index:9999 !important}` + React `ProfileMenu` JS detecta `document.body.classList.contains('sidebar-minimized')` → `position:fixed left 88 bottom 20` / Vue rely on CSS `!important` override.

---

## 10. Variables de Entorno

**Raíz `.env` / `.env.example`:**
```ini
POSTGRES_USER=clipsai
POSTGRES_PASSWORD=changeme          # cambiar en prod
POSTGRES_DB=clipsai
POSTGRES_PORT=5432
POSTGRES_TZ=UTC
DATABASE_URL=postgresql+psycopg2://clipsai:changeme@db:5432/clipsai  # opcional, default usa db:5432
JWT_SECRET=changeme-32-chars-minimo  # openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
BACKEND_FASTAPI_PORT=8000
APP_ENV=development
# Motor IA (no commitear reales — ver Issue 13)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_VERSION=2023-06-01
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...
API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
MODEL=deepseek-chat
```

**Frontends `frontend_react/.env` y `frontend_vue/.env`:**
```ini
VITE_API_URL=http://localhost:8000
```

> `.env` y `frontend_*/.env` están gitignored (solo `.env.example`). Si usas puerto distinto, añade a `allow_origins` en `backend_fastapi/app/main.py`.

---

## 11. Guía de Instalación

### Requisitos
Node 18+ (probado 18/20/22/24), npm 9+, Docker + Compose v2, Python 3.10+ (solo motor fuera de Docker), FFmpeg último.

### A) Infra + Backend (Docker)
```bash
cp .env.example .env          # editar POSTGRES_* y JWT_SECRET
docker compose up -d
docker compose up -d --build backend_fastapi   # tras editar app/main.py
curl http://localhost:8000/health              # {"status":"ok"}
curl http://localhost:8000/docs                # Swagger
curl -i -X OPTIONS http://localhost:8000/auth/registro \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST"     # 200 CORS
docker compose logs -f backend_fastapi
docker compose logs -f db
docker compose restart backend_fastapi         # tras CORS/redirect_slashes
docker compose down                            # mantiene postgres_data
docker compose down -v                         # borra DB (¡cuidado!)
```

### B) Frontend React
```bash
cd frontend_react
npm install
npm run dev                # http://localhost:3000 (proxy /api→:8000 si VITE_API_URL vacío)
npm run typecheck          # tsc --noEmit
npx tsc -b                 # build check
npm run build              # tsc -b && vite build → dist/
npm run preview -- --port 3000
```

### C) Frontend Vue
```bash
cd frontend_vue
npm install
npx vue-tsc --noEmit
npm run typecheck
npm run dev                # :5173 por defecto; --port 3001 para lado a lado con React
npm run build              # vue-tsc --noEmit && vite build → dist/
npm run preview -- --port 3001
```
> Puertos lado a lado recomendados: React :3000, Vue :3001/:5173, FastAPI :8000 (ya en allow_origins).

### D) Motor Python (fuera de Docker)
```bash
pip install -r backend_fastapi/requirements.txt
# + pip install librosa faster-whisper scikit-learn numpy opencv-python pydub requests anthropic
sudo apt-get install ffmpeg   # o brew/choco
python main.py video.mp4 transcripcion.txt
python engine.py video.mp4 transcripcion.txt --json
python ejemplo_engine.py video.mp4 transcripcion.txt
python limpiar.py           # borra audio.mp3, clips/, __pycache__
```

---

## 12. Flujo de Prueba

**Tres terminales lado a lado:**
```bash
# T1 infra
docker compose up -d && docker compose logs -f backend_fastapi
# T2 React :3000
cd frontend_react && npm run dev
# T3 Vue :3001
cd frontend_vue && npm run dev -- --port 3001
```

**Repetir en ambos frontends contra mismo :8000:**
1. **Registro** `/auth` → Registrarse `test@clipsai.com / Test12345!` → 201. Repetir → 409.
2. **Login** Iniciar Sesión → JWT en `localStorage clipsai_token`. Pass mal → 401.
3. **Persistencia** F5 en `/upload` → sigue auth (revalida `/auth/me`, spinner `isLoading`).
4. **Subida** `/upload` → video.mp4 + transcript.txt → `Subiendo archivos...` → `Iniciando procesamiento...` (pulse). Network `POST /videos 201` → `POST /videos/{id}/jobs 202`.
5. **Tracking** redirect `/jobs/{jobId}` → polling `GET /jobs/{id}` cada 2s: `PENDING` ámbar En cola → `PROCESSING` sky Procesando → `COMPLETED` verde + `X clips · motor: simulated` + cards `titulo | inicio-fin | Score | preview | Modo simulado` — `FAILED` rojo con `error_message`.
6. **Biblioteca** `/clips` toolbar 1 fila: buscar (debounce 350ms → ?q=), filtros score/sort, toggle grid/list, paginación page/limit 10.
7. **Dashboard** `/dashboard` KPIs + charts (si no datos → empty CTA Subir primer video).
8. **Settings** `/settings` editar perfil/avatar/theme + cambiar password → logout.
9. **Logout** limpia localStorage → /auth.

**Sin UI:**
```bash
curl -X POST http://localhost:8000/auth/registro -H "Content-Type: application/json" -d '{"email":"test@clipsai.com","password":"Test12345!"}'
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"test@clipsai.com","password":"Test12345!"}' | jq -r .access_token)
curl http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

---

## 13. API Endpoints

| Método | Ruta | Auth | Descripción | Códigos |
|--------|------|------|-------------|---------|
| GET | `/health` | — | `{status:"ok"}` | 200 |
| POST | `/auth/registro` | — | `UsuarioCreate {email,password≥8,full_name?}` | 201, 409 email existe, 422 validación |
| POST | `/auth/login` | — | JSON `{email,password}` → `{access_token, token_type:"bearer"}` | 200, 401 credenciales inválidas |
| POST | `/auth/login/form` | — | `OAuth2PasswordRequestForm` username=email | 200 (Swagger Authorize) |
| GET | `/auth/me` | Bearer | `UsuarioRead` | 200, 401 |
| POST | `/videos` | Bearer | `multipart video (.mp4/.mov/.avi ≤500MB) + transcription (.txt/.srt)` → `VideoResponse` guarda `UPLOAD_DIR`, persiste `transcript[:50k]` | 201, 400 formato, 401 |
| GET | `/videos` | Bearer | Lista usuario order `created_at DESC` | 200 |
| POST | `/videos/{videoId}/jobs` | Bearer | Crea Job pending + BackgroundTasks `_run_job` → `JobResponse` | 202, 403 video ajeno, 404 |
| GET | `/jobs/{jobId}` | Bearer | `JobResponse` status UPPER, `result_metadata.clips`, `error_message` | 200, 404 |
| GET | `/clips` | Bearer | Biblioteca: `q, min_score 0-100, sort_by (created_at_desc/asc, score_desc/asc), page, limit 1-100, video_id, status` → `ClipListResponse {items,total,page,limit,total_pages}` | 200 |
| GET | `/clips/{id}` | Bearer | `ClipResponse` ownership | 200, 404 |
| PATCH | `/clips/{id}` | Bearer | `{title?, tags?}` | 200, 404 |
| DELETE | `/clips/{id}` | Bearer | borra archivo físico si existe | 204, 404 |
| GET | `/clips/{id}/descarga` | Bearer | `FileResponse` o dummy `/tmp/clip_{id}.txt` | 200, 404 |
| GET | `/jobs/{id}/export?format=csv\|json` | Bearer | `Content-Disposition attachment` | 200, 422 |
| GET | `/clips/export?format=csv\|json` | Bearer | idem | 200 |
| GET | `/metrics` + `/api/metrics` | Bearer | `total_jobs, total_clips, total_minutes_processed, time_saved_hours, platform_distribution, recent_activity[7]` | 200 |
| GET | `/stats/summary` | Bearer | `total_videos, total_clips, avg_score, estimated_time_saved_minutes, score_distribution, recent_job` | 200 |
| GET | `/users/me`, `/me`, `/api/users/me` | Bearer | `UserResponse` | 200 |
| PUT/PATCH | `/users/me`, `/me` | Bearer | `UserUpdate` (email, full_name, avatar_url http, theme) | 200, 409 email tomado |
| POST | `/users/me/change-password` (+ `PUT /me/password`) | Bearer | `{current_password, new_password 8-128}` | 200, 400 |

**Docs interactivos:** `http://localhost:8000/docs` (Swagger) y `/redoc`, `/openapi.json`.

---

## 14. Scripts

| Script | Uso |
|--------|-----|
| `scripts/verify-auth.sh` | prueba registro/login/me |
| `scripts/verify-db.sh` | `psql \dt` + `\d usuarios/videos/jobs/clips` |
| `scripts/verify-issue4.sh` | POST /videos + polling jobs |
| `scripts/verify-issue5.sh` | CRUD clips |
| `limpiar.py` | borra `audio.mp3/.wav, audio.json, momentos_virales.json, transcripcion*, clips/, __pycache__, *.pyc` |
| `backend_fastapi/app/services/engine.py` | modo simulado vs real (detectar import main) |

---

## 15. Testing

- **Typecheck:** `cd frontend_react && npm run typecheck` (`tsc --noEmit` strict `noUnusedLocals/Parameters`), `cd frontend_vue && npm run typecheck` (`vue-tsc --noEmit`). Ambos pasan tras rediseño.
- **Build:** `npm run build` → `dist/` (`tsc -b && vite build` / `vue-tsc --noEmit && vite build`).
- **Infra:** `docker compose logs -f db`, `pg_isready` healthcheck, `curl /health`.
- **Manual:** flujo §12 en ambos frontends contra mismo backend; Network tab verificar polling 2s y `result_metadata.clips`.

---

## 16. Roadmap

Estado detallado y próximas issues en **[ISSUES.md](./ISSUES.md)** (14 issues originales + 8 nuevas). Resumen: Issues 1-5, 7, 14 completas; 6, 8, 9, 13 parciales; 10-12 pendientes (subtítulos, hook, publicación redes). Nuevas: completar compose, wire motor real, toolbar ya hecho, etc.

---

## 17. Licencia

Uso interno / académico — sin licencia pública. No subir secretos a Git. Ver `.gitignore` (`node_modules/`, `.env`, `dist/`, `__pycache__/`, `clips/`, `audio.mp3/json`, etc.) y `git check-ignore -v`.

> ¿Dudas sobre `opencode`? `/help` o reportar en https://github.com/anomalyco/opencode/issues

