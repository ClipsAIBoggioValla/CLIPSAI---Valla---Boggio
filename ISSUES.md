# ClipsAI — Diseño de Issues (Trabajo Final Programación 3) — Estado Actualizado Nov 2026

> Flujo de trabajo: cada issue arranca en rama propia desde `main` (`tipo/nombre-issue`), commits **Conventional Commits** (`feat:`, `fix:`, `chore:`), PR hacia `main` con evidencias. Orden sugerido por dependencias.

**Leyenda estado:**
- ✅ **Completado** — implementado, testeado manual/E2E, en `main` o listo para merge
- ⚠️ **Parcial** — implementado al 40-80%, gaps documentados
- ❌ **Pendiente** — no iniciado o solo stub/simulado
- 🆕 **Nuevo** — propuesto a partir del rediseño 2026 y gaps detectados

**Resumen ejecutivo:**
| Estado | Issues | Lista |
|--------|--------|-------|
| ✅ Completado | 9 | 1, 2, 3, 4, 5, 7, 14, 17, 18 |
| ⚠️ Parcial | 4 | 6, 8, 9, 13 |
| ❌ Pendiente | 3 | 10, 11, 12 |
| 🆕 Nuevos propuestos | 8 | 15–22 |

---

## Estado Global por Área

| Área | Estado | Detalle |
|------|--------|---------|
| Infra DB + Docker | ✅ | Postgres 15 + volumen + healthcheck + 01-init-schema.sql idempotente + triggers |
| Motor IA (Python) | ✅ | `main.py` pipeline completo + `engine.py` wrapper estable + `engine_subprocess.py` |
| FastAPI (referencia) | ✅ | 22 endpoints, auth JWT, videos/jobs/clips, export, metrics, stats, docs Swagger |
| Express (espejo) | ⚠️ ~35% | solo lectura clips/metrics/stats/users; faltan auth/videos/jobs + CRUD :id + Dockerfile |
| React | ✅ ~95% | Auth, Upload dropzone neon, JobStatus polling, Dashboard recharts, Biblioteca 1 fila, Settings, Layout cyber-tech |
| Vue | ✅ ~95% | Paridad 1:1 React (Pinia/axios, barras CSS, guards) |
| Diseño Cyber-Tech | ✅ | spark.css dark #0B0F17/#080C14/#121824 + lime #B4F105, avatar gradient, sidebar fix, dropzone glow, dashboard oscuro |
| Subtítulos/Hook/Publicación | ❌ | no implementados (editor_viral placeholder, engine simulado, sin endpoint publicar) |
| Seguridad | ⚠️ | JWT/bcrypt OK pero `.env.example` filtra ANTHROPIC_API_KEY, falta rotación |
| Compose completo | ❌ | solo db+backend_fastapi, faltan backend_express + frontends |

---

## Issues Originales (1–14) — Actualizado

### Issue 1 — Infraestructura: DB dockerizada y esquema inicial — ✅ Completado

**Descripción:** Levantar PostgreSQL vía Docker con volumen persistente y crear esquema inicial.

**Objetivo:** Base funcional para que backends se apoyen.

**Alcance incluido:** `docker-compose.yml` Postgres + volumen `postgres_data`; `init-scripts/01-init-schema.sql` tablas `usuarios`, `videos`, `jobs`, `clips` + FKs + CHECK + índices + triggers `set_updated_at()`.

**Archivos:** `docker-compose.yml`, `init-scripts/01-init-schema.sql`, `init-scripts/README.md`

**Dependencias:** Ninguna.

**Criterios cumplidos:**
- [x] `docker compose up -d` levanta Postgres `pg_isready -U $POSTGRES_USER` healthy
- [x] `\dt` + `\d` muestran 4 tablas + FK Job→Video, Clip→Job, Video→Usuario
- [x] `down && up` mantiene datos (volumen nombrado)

**Evidencias registradas:** `scripts/verify-db.sh` (`psql \dt`), captura `postgres_data` sobreviviendo reinicio.

**Deuda:** faltan columnas evolutivas en SQL — hoy se añaden por `ALTER IF NOT EXISTS` en runtime (ver Issue 13).

---

### Issue 2 — Contrato estable del motor de clipsai — ✅ Completado

**Descripción:** Envolver `main.py` + `audio_analyzer.py` + `whisper_transcriber.py` + `editor_viral.py` en interfaz estable `(video, transcripcion)` sin tocar lógica interna, eliminando presets podcast/gaming.

**Objetivo:** Desacoplar motor de capa web via flujo estandarizado.

**Alcance incluido:** `engine.py:procesar_video(video_path, transcripcion_path) → ProcesamientoResultado {exito, clips: ClipInfo[], carpeta_salida, error, error_tipo, error_detalle}` + dataclasses `ClipInfo {archivo,inicio,fin,titulo_sugerido,hook_texto,criterio_principal,score,primer_segundo,motivo}` + `engine_subprocess.py` por `subprocess.run --json` con timeout 600s.

**Archivos:** `engine.py` (378L), `engine_subprocess.py` (183L), `ENGINE_USO.md` (tabla error_tipo→HTTP), `ejemplo_engine.py`

**Criterios cumplidos:**
- [x] Un único punto de entrada con dos paths (ver `ENGINE_USO.md`)
- [x] Errores estructurados nunca `sys.exit()` — `error_tipo: ValidacionError|DependenciaError|AudioError|TranscripcionError|PreparacionIAError|ConexionError|TimeoutError|IAError|GeneracionError|SinClipsValidos|ErrorInterno` + traceback

**Pendiente para cerrar 100%:** wirear `run_clip_engine` en FastAPI para dejar de simular (ver Issue 15).

---

### Issue 3 — Backend #1 (FastAPI): autenticación — ✅ Completado

**Descripción:** Registro/login JWT.

**Archivos:** `backend_fastapi/app/routers/auth.py`, `security/hashing.py` (bcrypt truncate 72 bytes), `security/jwt.py` (python-jose HS256 60min), `deps.py` (HTTPBearer + get_current_user), `schemas/usuario.py`, `models/usuario.py`

**Endpoints:** `POST /auth/registro 201 UsuarioRead / 409 / 422`, `POST /auth/login JSON {email,password} → Token`, `POST /auth/login/form OAuth2 (para Swagger)`, `GET /auth/me` Bearer

**Criterios:**
- [x] registro→login→JWT válido
- [x] ruta protegida 401 sin/inválido

**Evidencias:** `scripts/verify-auth.sh` + curl + `http://localhost:8000/docs` Authorize.

---

### Issue 4 — Backend #1 (FastAPI): subida de video y disparo de Job — ✅ Completado

**Descripción:** `POST /videos` multipart + `POST /videos/{id}/jobs` async + `GET /jobs/{id}`.

**Archivos:** `backend_fastapi/app/routers/videos.py` (valida ext .mp4/.mov/.avi + .txt/.srt, tamaño 500MB streaming 1MB chunks, `UPLOAD_DIR`, transcript 50k chars), `routers/jobs.py` (ownership 403, 404, `BackgroundTasks.add_task(_run_job)`, status `pending→processing→completed|failed`, result_metadata.clips dummy o real)

**Criterios:**
- [x] No bloquea request (202 antes de FFmpeg)
- [x] Pasa por pending→processing→completed/failed (polling 2s)
- [x] Rechazo formato inválido con mensaje claro

**Evidencias:** `scripts/verify-issue4.sh` polling `GET /jobs/{id}`, `JobStatusPage` React/Vue.

---

### Issue 5 — Backend #1 (FastAPI): CRUD de Clips — ✅ Completado

**Descripción:** `GET /clips`, `PATCH /clips/{id}`, `DELETE /clips/{id}`, `GET /clips/{id}/descarga`.

**Archivos:** `routers/clips.py` (join Clip→Job→Video filtra `usuario_id`, `q ilike title/transcript`, `min_score 0-100`, `sort_by`, `page/limit`, `video_id/status`, `LEFT(transcript,500)`, count total), `schemas/clip.py`, `models/clip.py`

**Criterios:**
- [x] CRUD crear (vía Job) → listar → editar metadata → eliminar (cascade)
- [x] 403/404 si clip de otro usuario (ownership via `video.user_id` o `job.video_id`)
- [x] descarga `FileResponse` + dummy `/tmp/clip_{id}.txt` si storage vacío

**Evidencias:** `scripts/verify-issue5.sh` + `GET /clips?video_id=&status=` + PATCH/DELETE entre usuarios.

---

### Issue 6 — Backend #2 (Express): paridad completa con FastAPI — ⚠️ Parcial (~35%)

**Descripción:** Reimplementar mismos endpoints/contratos contra misma DB.

**Estado actual:** `backend_express/src/app.ts` + `routes/clips|export|metrics|stats|users`, `db/index.ts` (Pool + normaliza `postgresql+psycopg2://`), `middleware/auth.ts` (jwt.verify, fallback `changeme` inseguro)

| Ruta | FastAPI | Express | Estado |
|------|---------|---------|--------|
| `POST /auth/registro,login, me` | ✅ | ❌ no existe `routes/auth.ts` | 0% |
| `POST /videos, GET /videos` | ✅ | ❌ no existe `routes/videos.ts` + multer | 0% |
| `POST /videos/{id}/jobs, GET /jobs/{id}` | ✅ | ❌ no existe `routes/jobs.ts` + Background | 0% |
| `GET /clips` (q,min_score,sort_by,page,limit,video_id,status) | ✅ | ⚠️ falta `video_id,status` | 70% |
| `GET/PATCH/DELETE /clips/:id, descarga` | ✅ | ❌ | 0% |
| `export, metrics, stats, users, health` | ✅ | ✅ ~95% | OK |

**Archivos faltantes:** `src/routes/auth.ts`, `videos.ts` (multer), `jobs.ts` (setImmediate + runClipEngine portado), completar `clips.ts` CRUD, `src/services/engine.ts`, `Dockerfile`, entrada en `docker-compose.yml`.

**Dependencias:** 3,4,5.

**Criterios pendientes:**
- [ ] Cada endpoint misma forma que FastAPI
- [ ] Mismo JWT funciona indistinto en ambos

**Acción:** ver **Issue 15** (desglose).

---

### Issue 7 — Frontend #1 (React): auth, subida y seguimiento de Jobs — ✅ Completado

**Descripción:** Login/registro, subida video+transcripción, job tracking.

**Archivos:** `frontend_react/src/pages/AuthPage.tsx` (tabs login/register, alerts 401/409/422, showPassword, full_name), `pages/UploadPage.tsx` (dropzone neon `dropzone-neon` dashed lime glow, file inputs, `videoService.upload` → `jobService.createJob` → `/jobs/:id`, progress pulse), `pages/JobStatusPage.tsx` (StatusBadge PENDING ámbar/PROCESSING sky spinner/COMPLETED verde/FAILED rojo, `result_metadata.clips`), `context/AuthContext.tsx` (localStorage `clipsai_token`, init `/auth/me`), `hooks/useJobPolling.ts` 2000ms

**Criterios:**
- [x] flujo registro→login→subir→ver status sin reload
- [x] validación muestra errores claros

**Evidencias:** grabaciones flujo + Network `POST /videos 201 → 202 → GET /jobs 2s`.

---

### Issue 8 — Frontend #1 (React): gestión y publicación de Clips — ⚠️ Parcial (~85%)

**Descripción:** Biblioteca con filtros, edición, borrado, descarga, publicar redes.

**Estado:** Biblioteca completa (ver Issue 18) con toolbar 1 fila, filtros `q/min_score/sort_by/page/limit`, `viewMode grid|list`, `clip-card hover neón`, `score-badge-neon`, `table-custom`, paginación. Dashboard recharts, Settings. **Falta:** modal/botón "Publicar en Redes" + wiring `POST /clips/{id}/publicar` (Issue 12) + edición inline/borrado con confirmación y descarga desde UI (endpoints existen pero no expuestos en biblioteca).

**Archivos:** `pages/ClipLibraryPage.tsx` (+ duplicado `LibraryPage.tsx`), `components/ExportDropdown.tsx` (csv/json), `pages/DashboardPage.tsx`, `pages/SettingsPage.tsx`

**Criterios parciales:**
- [x] Listar con filtros y paginación punta a punta
- [ ] Editar/borrar/publicar desde UI (parcial — export dropdown sí, publish no)

**Dependencias:** 5, 7.

---

### Issue 9 — Frontend #2 (Vue): paridad completa con React — ⚠️ Parcial (~95%)

**Descripción:** Reimplementar vistas React en Vue.

**Archivos:** `frontend_vue/src/views/AuthView.vue` (`<script setup>`, v-model), `UploadView.vue`, `JobStatusView.vue`, `DashboardView.vue` (barras CSS, no recharts), `ClipLibraryView.vue` (+ `LibraryView.vue` duplicado), `SettingsView.vue`, `NotFoundView.vue`, `stores/auth.ts` Pinia, `composables/useJobPolling.ts` getter, `api/client.ts` axios interceptors, `router/index.ts` beforeEach, `components/Layout.vue/Sidebar.vue/Navbar.vue` etc.

**Tabla paridad:**
| Dimensión | React | Vue | Estado |
|-----------|-------|-----|--------|
| HTTP | fetch | axios | OK divergencia técnica |
| Auth | Context | Pinia | OK |
| Upload/Job | manual | Composition | 100% |
| Dashboard | recharts | CSS | visual parcial |
| Biblioteca | toolbar 1 fila (Issue 18) | idem 1 fila | 100% |
| Avatar gradient | ✅ | ✅ | OK |
| Vite | port 3000 proxy /api | port 3000 sin proxy | divergencia menor |

**Criterios:**
- [x] Mismo flujo y vistas contra mismo backend
- [ ] Dashboard librería idéntica (recharts vs div)

**Evidencias:** capturas lado a lado cada vista (auth/upload/job/dashboard/biblioteca/settings).

---

### Issue 10 — Feature: subtitulado automático (burned-in) — ❌ Pendiente

**Descripción:** Subtítulos quemados palabra por palabra via FFmpeg/MoviePy.

**Estado:** `editor_viral.py` declara `"sin subtítulos"` + `backend_fastapi/app/services/engine.py` simulado nunca genera `.srt/.ass`. No hay filter `subtitles`.

**Alcance incluido:** generar `.srt` desde `whisper_words.json` + `ffmpeg -vf subtitles=...:force_style='Fontsize=24,PrimaryColour=&H00FFFFFF,BorderStyle=3'` + referenciar en `Clip.file_path`.

**Criterios pendientes:**
- [ ] Cada clip incluye subtítulos legibles sincronizados

**Dependencias:** 2,5.

**Propuesta cerrar:** ver **Issue 19**.

---

### Issue 11 — Feature: generación de hook inicial — ❌ Pendiente

**Descripción:** Detectar fragmento mayor energía y anteponer al inicio del clip.

**Estado:** `main.py` genera `hook_texto` y `primer_segundo` pero `validar_clips` y `editor_viral.procesar_clip` no reordenan; no hay scoring hook.

**Alcance:** lógica en motor reutilizando `audio_analyzer` (intensidad >7) + `score` LLM → identificar 3-5s hook → `ffmpeg concat` hook+clip.

**Criterios pendientes:**
- [ ] Clip arranca con segmento hook
- [ ] Hook score > promedio clip

**Dependencias:** 2.

**Propuesta cerrar:** ver **Issue 19**.

---

### Issue 12 — Feature: subida automática a redes sociales — ❌ Pendiente

**Descripción:** `POST /clips/{id}/publicar` {plataforma, metadata} → subida async → `publication_status=published` + URL/ID externo.

**Estado:** no existe router ni servicio ni botón UI. `ExportDropdown` solo csv/json. `Clip` tiene `social_network` + `publication_status` DDL pero nunca actualizado por endpoint.

**Alcance:** endpoint FastAPI+Express, integración TikTok/IG/YouTube Shorts (o webhook mock), actualización `published_at`, UI modal Publicar.

**Criterios pendientes:**
- [ ] Endpoint publica y guarda link
- [ ] UI refleja `publicado`

**Dependencias:** 5,10,11.

**Propuesta cerrar:** ver **Issue 20**.

---

### Issue 13 — Seguridad y empaquetado final — ⚠️ Parcial

**Descripción:** Eliminar secretos hardcodeados y completar `docker-compose.yml`.

**Estado:**
- JWT/bcrypt, variables entorno, `.gitignore` (`node_modules/`, `.env`, `dist/`, `__pycache__/`, `clips/`) OK.
- ❌ **Secreto filtrado:** `.env.example` y `.env` contienen `ANTHROPIC_API_KEY=sk-ant-api03-...` real (git history). `JWT_SECRET` débil `changeme`. `requirements.txt` lista `passlib[bcrypt]` no usado, falta `bcrypt` y `python-dotenv`.
- ❌ **Compose incompleto:** solo `db` + `backend_fastapi`; faltan `backend_express` + `frontend_react` + `frontend_vue` (PROYECTO.md promete `docker compose up` <2min con todo).
- ❌ No hay `backend_express/Dockerfile`.

**Criterios pendientes:**
- [ ] `git grep -i "sk-ant\|api_key"` vacío (rotar key + filter-repo)
- [ ] `docker compose up` levanta DB+2 backends+2 frontends

**Acción:** ver **Issue 21**.

---

### Issue 14 — Documentación de API (OpenAPI/Swagger) — ✅ Completado

**Descripción:** Spec OpenAPI en ambos backends.

**Estado:** FastAPI expone `/docs` (Swagger) + `/redoc` + `/openapi.json` auto-generado Pydantic. Todos los routers con tags y response models. Express **no** tiene Swagger (ver Issue 15/22). Para FastAPI criterio cumplido.

**Archivos:** `backend_fastapi/app/main.py` (`title="ClipsAI", version="0.1.0"`), cada `APIRouter` con `summary`.

**Criterios:**
- [x] FastAPI `/docs` actualizada (incluye jobs/clips/export/metrics/stats)
- [ ] Express `/api-docs` pendiente

---

## Nuevos Issues Propuestos (15–22) — Para Seguir Armando Backlog

### Issue 15 — Completar paridad Express (auth + videos + jobs + CRUD clips) — 🆕 Pendiente (prioridad ALTA)

**Descripción:** Llevar Express de 35% → 100% paridad.

**Alcance incluido:**
- `src/routes/auth.ts`: `POST /auth/registro` (bcryptjs hash, SELECT email 409, INSERT, 201), `POST /auth/login` (compare, sign HS256 60min), `GET /auth/me` (middleware), `POST /auth/login/form` (OAuth2 body `username`)
- `src/routes/videos.ts`: `multer` memoryStorage, valida ext/tamaño 500MB, guarda `UPLOAD_DIR` o `./storage/uploads`, `INSERT videos`, `GET /videos`
- `src/routes/jobs.ts`: `POST /videos/:id/jobs` (ownership 403, INSERT pending, `setImmediate(_runJob)`), `GET /jobs/:id` (join usuario check 404), `_runJob` port de `services/engine.ts` simulado + normalización `HH:MM:SS→sec` + `INSERT clips`
- Completar `routes/clips.ts`: `video_id` + `status` filters, `GET/PATCH/DELETE /clips/:id`, `GET /clips/:id/descarga` (FileResponse o dummy)
- `src/services/engine.ts` port de `run_clip_engine`
- Validación UUID 422 uniforme, EmailStr con regex, password 8-128
- `Dockerfile` node:20-alpine + `docker-compose.yml` service `backend_express:3001`

**Alcance excluido:** features nuevas (subtítulos/hook).

**Dependencias:** 1,2,3,4,5

**Criterios:**
- [ ] `diff` responses FastAPI vs Express idéntico (excepto `created_at` timestamps)
- [ ] `curl` mismo JWT funciona contra :8000 y :3001
- [ ] `npm run typecheck` + `docker compose up backend_express` healthy

**Estimación:** 2–3 días.

---

### Issue 16 — Wirear motor real en FastAPI (`backend_fastapi/app/services/engine.py`) — 🆕 Pendiente (ALTA)

**Descripción:** Cambiar `run_clip_engine` de simulado (sleep+dummy) a `engine.py:procesar_video` real o `engine_subprocess`.

**Alcance incluido:**
- Import `from engine import procesar_video` si `ANTHROPIC_API_KEY` y `ffmpeg` disponibles, sino fallback simulado con flag `engine: simulated|real`
- Opción `ENGINE_MODE=real|simulated` en `.env`
- Mover `clips` de `/tmp/clipsai_*` a `storage/clips/{job_id}/` y persistir `file_path` real
- Manejar `ProcesamientoResultado.error_tipo` → `job.error_message` + `status=failed` + HTTP 422 si `SinClipsValidos`
- Añadir `ffmpeg`, `librosa`, `faster-whisper`, `torch` al `Dockerfile` (multi-stage o `python:3.11-slim` + apt)

**Alcance excluido:** subtítulos/hook (Issues 19).

**Dependencias:** 2,4

**Criterios:**
- [ ] `POST /videos/{id}/jobs` con video real genera `.mp4` recortados verificables `ffprobe duration 30-90s`
- [ ] `JobStatusPage` deja de mostrar `Modo simulado` cuando `engine: real`
- [ ] Fallo IA (key inválida) → `FAILED` con `error_tipo=ConexionError` visible

---

### Issue 17 — Rediseño Cyber-Tech Dark Mode unificado — ✅ Completado (Nov 2026)

**Descripción:** Transformar UI light (`#F4F6F5`, `border-black`, `bg-white`) en SaaS dark neón.

**Implementado:**
- `frontend_react/src/styles/spark.css` + `frontend_vue/src/assets/spark.css` unificados: `:root` `--bg-app:#0B0F17`, `--bg-sidebar:#080C14`, `--bg-card:#121824`, `--border-subtle:rgba(255,255,255,0.08)`, `--brand-lime:#B4F105`, `--text-primary:#F1F5F9`, `--text-secondary:#94A3B8`, glows `0 0 20px rgba(180,241,5,0.35)`
- Sidebar `#080C14 border-r #1f2937`, active `rgba(180,241,5,0.12)` + glow, `sidebar-wrapper overflow:visible` + `body.sidebar-minimized .dropdown-menu-profile {position:fixed left:88px bottom:20px z-9999}` + React `ProfileMenu` JS fixed
- Navbar `#080C14 backdrop-blur`, btn `bg #B4F105 text #080C14 glow`, search `bg #121824 focus lime`
- Cards `bg #121824 border subtle shadow-xl`, `clip-card hover border lime/35 + bg #161E2E + lift`, `kpi-card` top-line lime, `score-badge-neon high/mid/low`
- Dropzone `dropzone-neon dashed lime 0.35 + radial glow`, icon 52px
- Login dark radial gradients, inputs `bg #0B0F17 focus lime`, `btn-login lime glow`
- Avatar gradient `from-emerald-500 to-[#B4F105] text-[#080C14]`
- Dashboard oscuro unificado, charts `bg #121824`, barras `rgba(255,255,255,0.06)`
- **Builds pasan:** `React tsc --noEmit` + `Vue vue-tsc --noEmit` + `vite build`

**Archivos:** ambos `spark.css`, `Avatar.*`, `ProfileMenu.tsx`, `Sidebar.tsx/.vue`, `clip-card`, `DashboardPage/View`, `UploadPage/View`, `ClipLibraryPage/View`, `SettingsPage/View`, `AuthPage/View`

**Dependencias:** 7,9

**Evidencias:** `npm run build` + capturas dark mode + revisión `git diff spark.css`.

---

### Issue 18 — Refactor Biblioteca filtros a toolbar compacta 1 fila — ✅ Completado (Nov 2026)

**Descripción:** Convertir filtros de bloque alto (`card-spark` + `flex-col gap-4` ~120px) en barra horizontal compacta ~56px.

**Implementado (React `ClipLibraryPage.tsx` + `LibraryPage.tsx`, Vue `ClipLibraryView.vue` + `LibraryView.vue`):**
- Contenedor `flex flex-col md:flex-row items-center justify-between gap-4 p-3 bg-[#121824] rounded-xl border border-white/10` `min-height:56px`
- Izquierda `relative flex-1 max-w-md w-full` + `<i class="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">` + `input w-full pl-9 pr-4 py-2 bg-[#0B0F17] border-white/10 rounded-lg text-sm placeholder-gray-400 focus:border-[#B4F105]`
- Derecha `flex items-center gap-3 w-full md:w-auto justify-end` + selects `bg-[#0B0F17] text-xs border-white/10 rounded-lg px-3 py-2 hover:border-white/20` + toggle `py-1 px-1 bg-[#0B0F17] border-white/10 rounded-lg flex gap-1` botones `rounded-md`
- `hasFilters` movido fuera como `flex gap-2 mb-3` con `text-[#94A3B8]`

**Criterios:**
- [x] Desktop: 1 fila, ≤56px alto, sin overflow
- [x] Mobile: stack `flex-col` con búsqueda full-width arriba, filtros abajo `justify-end`
- [x] `typecheck` OK ambos frontends

---

### Issue 19 — Implementar subtítulos burned-in + hook reordering — 🆕 Pendiente (MEDIA)

**Descripción:** Cerrar Issues 10 y 11 juntos.

**Alcance incluido:**
- **Subtítulos:** `whisper_transcriber.transcribir_video` ya genera `whisper_words.json` con `word, start, end`. Crear `generar_srt(words, out.srt)` + `editor_viral._quemar_subtitulos(clip.mp4, srt)` con `ffmpeg -vf subtitles=out.srt:force_style='FontName=Plus Jakarta Sans,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=36'`.
- **Hook:** `audio_analyzer` + LLM `primer_segundo` → extraer 3-5s segmento mayor `intensidad` dentro de cada clip → `ffmpeg concat` `hook.mp4 + clip_rest.mp4` con `loudnorm` uniforme. Almacenar `hook_start/end` en `clip.tags`.
- Persistir `file_path` final con subtítulos quemados.

**Dependencias:** 2,10,11,16

**Criterios:**
- [ ] `ffprobe` clip final 1080x1920, subtítulos visibles en frames sample
- [ ] Duración total 30-90s (hook incluido)
- [ ] A/B sin hook vs con hook demuestra retención esperada (score hook > promedio)

---

### Issue 20 — Publicación automática a redes + UI — 🆕 Pendiente (MEDIA)

**Descripción:** Cerrar Issue 12.

**Alcance incluido:**
- **Backend:** `POST /clips/{id}/publicar {platform: tiktok|youtube_shorts|instagram_reels, title?, description?, schedule_at?}` → valida ownership, encola `BackgroundTasks`, mock o real API (si credenciales `TIKTOK_CLIENT_KEY` etc. en `.env`), `UPDATE clips SET social_network, publication_status='published', published_at=NOW()` + guarda `external_url` en `tags`, `GET /clips/{id}/publicacion` status.
- **Frontend:** `ClipLibraryPage` card footer `Publicar` dropdown (TikTok/YouTube/IG) → modal confirma → `clipService.publish(id, platform)` → badge `published` verde + link externo, toast success/error.
- **Migrations:** ya existe `social_network` + `publication_status` CHECK, solo usarlos.

**Dependencias:** 5,8,9

**Criterios:**
- [ ] `curl POST /clips/{id}/publicar` → `published` + `external_url` mock `https://tiktok.com/@...`
- [ ] UI badge cambia `draft → published` sin reload

---

### Issue 21 — Seguridad, limpieza y compose completo — 🆕 Pendiente (ALTA)

**Descripción:** Cerrar Issue 13 definitivamente.

**Alcance incluido:**
- Rotar `ANTHROPIC_API_KEY` (revocar `sk-ant-api03-...`), `git filter-repo` o `BFG` para purgar historia, `.env.example` con placeholders `ANTHROPIC_API_KEY=changeme`, añadir `.env` a `.gitignore` ya existente verificado `git check-ignore -v`.
- `backend_fastapi/requirements.txt`: añadir `bcrypt==4.1.2`, `python-dotenv==1.0.1`, quitar `passlib[bcrypt]` o usarlo; pin de versiones.
- `backend_express/Dockerfile` `node:20-alpine` + `npm ci --production` + `CMD node dist/index.js`.
- `docker-compose.yml` completo: `db` + `backend_fastapi:8000` + `backend_express:3001` + `frontend_react:3000` (build `vite preview`) + `frontend_vue:3002` + `depends_on healthy`, `env_file .env`, networks `clipsai-net`.
- `scripts/verify-compose.sh`: `compose up -d --build` + `curl /health` 3 servicios + `psql \dt`.

**Criterios:**
- [ ] `git grep -E "sk-ant|sk-proj|JWT_SECRET.*changeme"` solo en `.env.example` placeholders
- [ ] `docker compose up -d` levanta 5 servicios <2min, `docker compose ps` all healthy

---

### Issue 22 — Documentación, tests y observabilidad — 🆕 Propuesta (BAJA)

**Descripción:** Cerrar Issue 14 para Express + añadir tests y logs.

**Alcance incluido:**
- **Swagger Express:** `swagger-jsdoc` + `swagger-ui-express` en `backend_express`, `GET /docs` + `/api-docs` con spec OpenAPI 3.0 reflejando mismos schemas que FastAPI (usuario, video, job, clip, metrics).
- **Tests:** `backend_fastapi/tests/test_auth.py` (pytest), `frontend_react/src/__tests__/useJobPolling.test.tsx` (vitest), CI `npm run typecheck` + `pytest` en GitHub Actions.
- **Logs:** `structlog` FastAPI + `pino` Express, `GET /health` detalla `uptime, db_latency`.
- **README:** ya completado (ver `README.md` Nov 2026) — mantener sincronizado con `ISSUES.md`.

**Dependencias:** 6,13,15

**Criterios:**
- [ ] `http://localhost:3001/docs` Swagger Express con todos los endpoints
- [ ] `pytest -q` + `npm run typecheck` verde en CI

---

## Cómo Crear Nuevos Issues a Partir de Este Archivo

1. **Elige título** `feat: subtítulos burned-in` o `fix: sidebar overflow` y crea rama `feat/subtitulos-burned-in` desde `main`.
2. **Copia plantilla:**
   ```md
   ## Issue N — Título

   **Descripción:** Qué problema resuelve
   **Objetivo:** Métrica verificable
   **Alcance incluido:** archivos/ endpoints / UI
   **Alcance excluido:** qué no entra
   **Dependencias:** Issues previos
   **Criterios de aceptación:** checklist [] con comandos verificables
   **Evidencias:** capturas, curl, video
   ```
3. **Estima** (días) y prioridad (ALTA/MEDIA/BAJA) y asigna a milestone.
4. **PR:** incluye `Closes #N`, screenshots antes/después, `git diff --stat`, `npm run typecheck + build`, `docker compose` logs.
5. **Convenciones:** `feat:`, `fix:`, `chore:`, `docs:`, `refactor:` + scope (`frontend`, `backend`, `engine`, `infra`).

**Ideas para seguir armando backlog (a partir del README §3):**
- Paginación cursor vs offset en `/clips` para 10k+ clips
- Webhooks `POST /webhooks/job-completed` para notificar frontend via SSE/WebSocket en vez de polling 2s
- Rate limiting `express-rate-limit` + `slowapi` en FastAPI
- Upload directo a S3/MinIO en vez de `UPLOAD_DIR` local
- Editor timeline drag-drop para reordenar clips antes de export
- Multi-idioma `i18n` (react-i18next / vue-i18n)
- Roles `admin` vs `editor` (Issue 3 excluía roles)
- Analytics avanzado: retention heatmap por clip

---

## Dependencias Visuales

```
1 (DB) ─┬─→ 3 (Auth) ─→ 4 (Videos/Jobs) ─→ 5 (Clips) ─┬─→ 6 (Express)
        │                    │                        ├─→ 8 (React clips)
        └─→ 2 (Engine) ──────┘                        └─→ 7 (React upload) ─→ 9 (Vue)
                                                      10 (subs) ─┐
                                                      11 (hook) ─┤→ 12 (publicar) ─→ 13 (seguridad) ─→ 14 (docs)
                                                        17 (dark) ─→ 18 (toolbar) ─┐
                                                        15 (express full) ─→ 16 (wire engine) ─→ 19 (subs+hook) ─→ 20 (publish UI) ─→ 21 (compose) ─→ 22 (swagger+tests)
```

**Rama activa sugerida para próximos:** `feat/frontend-flujo-entrada` o `feat/compose-completo`.
