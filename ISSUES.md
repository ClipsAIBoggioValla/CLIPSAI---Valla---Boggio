# ClipsAI — Diseño de Issues (Trabajo Final Programación 3) — Estado Actualizado Sep 2026

> Flujo de trabajo: cada issue arranca en rama propia desde `main` (`tipo/nombre-issue`), commits **Conventional Commits** (`feat:`, `fix:`, `chore:`), PR hacia `main` con evidencias. Orden sugerido por dependencias.

**Leyenda estado:**
- ✅ **Completado** — implementado, testeado manual/E2E, en `main` o listo para merge
- ⚠️ **Parcial** — implementado al 40-80%, gaps documentados
- ❌ **Pendiente** — no iniciado o solo stub/simulado
- 🆕 **Nuevo** — propuesto a partir del rediseño 2026 y gaps detectados

## Sincronización GitHub — 21 Sep 2026

> Fuente: dos últimos listados GitHub (cerradas vs abiertas). Formato Markdown limpio con PR vinculados.

### Completadas [x] — cerradas en GitHub
- [x] Issue #30 — Swagger / OpenAPI 3.0 para Backend Express (#50) — `backend_express/src/docs/swagger.ts` `backend_express/src/app.ts` `/docs` + `/openapi.json`
- [x] Issue #29 — Integración de Subtítulos ASS y Hook Teaser en Pipeline FFmpeg (#49) — `backend_fastapi/app/routers/jobs.py` + `services/ffmpeg_service.py` + `services/ass_generator.py` + `services/hook_service.py`
- [x] Issue #28 — Vista de Gestión de Integraciones (/settings/integrations) (#48)
- [x] Issue #27 — Servicio de Publicación Real en APIs de Redes Sociales (#47)
- [x] Issue #26 — Flujo OAuth 2.0: Conector de TikTok (Content Posting API) (#46)
- [x] Issue #25 — Flujo OAuth 2.0: Conector de Meta (Instagram Graph API) (#45)
- [x] Issue #24 — Flujo OAuth 2.0: Conector de YouTube (Google Data API v3) (#44)
- [x] Issue #23 — Configuración de Túnel HTTPS Local (ngrok & Callbacks) (#43)
- [x] Issue #22 — Esquema de Base de Datos para Cuentas Sociales (#42) — `social_accounts` + `user_social_accounts`
- [x] Issue #21 — Cableado del Pipeline Backend, Engine de Renderizado y Routers FastAPI (#36) — `services/engine.py` real + `jobs._run_job` + `storage/clips`
- [x] Rediseñar el front-end siguiendo la estética de "Spark Admin" (Bootstrap 5) (#34) — `spark.css` `#0B0F17`/`#B4F105` (equiv. Issue 17)

### Pendientes [ ] — abiertas en GitHub
- [ ] Issue #31 — Eventos en Tiempo Real (SSE) para Estado de Publicación (#51)
- [ ] Issue #32 — Landing Page Pública e Index (/) (#52)
- [ ] Issue #33 — Páginas Legales para Validación de APIs (/privacy, /terms, /data-deletion) (#53)
- [ ] Issue #34 — Modo "Video de Muestra" en Pantalla de Carga (/upload) (#54)
- [ ] Issue #35 — Refactorización y Limpieza de Deuda Técnica en UI (#55)

**Resumen ejecutivo actualizado:**
| Estado | Issues | Lista |
|--------|--------|-------|
| ✅ Completado | 19 | 1, 2, 3, 4, 5, 7, 14, 17, 18, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30 (+ #34 Spark) |
| ⚠️ Parcial | 2 | 6, 13 (Express 35%→90% tras 30, Seguridad compose parcial) |
| ❌ Pendiente | 5 | 31, 32, 33, 34, 35 (activas GitHub #51–#55) |
| 🆕 Archivados | 3 | 8, 9, 10/11/12 cerrados vía 28/29/19 |

---

## Estado Global por Área

| Área | Estado | Detalle |
|------|--------|---------|
| Infra DB + Docker | ✅ | Postgres 15 + volumen + healthcheck + 01-init-schema.sql idempotente + triggers |
| Motor IA (Python) | ✅ | `main.py` pipeline completo + `engine.py` wrapper estable + `engine_subprocess.py` |
| FastAPI (referencia) | ✅ | 22 endpoints, auth JWT, videos/jobs/clips, export, metrics, stats, docs Swagger + **Issue 21 cableado engine real** |
| Express (espejo) | ✅ ~90% | Auth/videos/jobs/clips/metrics/stats/users + **Issue 30 Swagger /docs** `swagger-ui-express` + `swagger-jsdoc` |
| React | ✅ ~95% | Auth, Upload dropzone neon, JobStatus polling, Dashboard recharts, Biblioteca 1 fila, Settings, Layout cyber-tech |
| Vue | ✅ ~95% | Paridad 1:1 React (Pinia/axios, barras CSS, guards) |
| Diseño Spark Admin | ✅ | `spark.css` dark `#0B0F17/#080C14/#121824` + lime `#B4F105` — Issue #34 |
| Subtítulos/Hook | ✅ | **Issue 29** `ass_generator.generate_hooked_ass` + `ffmpeg_service.build_hook_clip` + `burn_subtitles` integrado en `jobs._run_job` con fallback degradado |
| Publicación | ✅ | **Issues 27–28** publicación real TikTok/YouTube/Instagram + **Issue 23** ngrok callbacks |
| OAuth | ✅ | **Issues 24–26** YouTube/Google, Instagram Graph, TikTok Content Posting |
| DB Cuentas Sociales | ✅ | **Issue 22** `social_accounts` schema + `user_social_accounts` |
| Seguridad | ⚠️ | JWT/bcrypt OK pero `.env.example` filtra ANTHROPIC_API_KEY, falta rotación `BFG` |
| Compose completo | ⚠️ | `db` + `backend_fastapi` + `backend_express` listo; frontends `preview` pendiente Issue 31–35 |
| Docs OpenAPI | ✅ | FastAPI `/docs` + Express `/docs` + `/openapi.json` paridad 1.0.0 |

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

---

### Issue 2 — Contrato estable del motor de clipsai — ✅ Completado

**Descripción:** Envolver `main.py` + `audio_analyzer.py` + `whisper_transcriber.py` + `editor_viral.py` en interfaz estable `(video, transcripcion)`.

**Archivos:** `engine.py` (378L), `engine_subprocess.py` (183L), `ENGINE_USO.md`, `ejemplo_engine.py`

**Criterios cumplidos:**
- [x] `engine.py:procesar_video` único punto de entrada
- [x] Errores estructurados `error_tipo: ValidacionError|...|SinClipsValidos` + traceback

---

### Issue 3 — Backend #1 (FastAPI): autenticación — ✅ Completado

**Archivos:** `backend_fastapi/app/routers/auth.py`, `security/hashing.py`, `security/jwt.py`, `deps.py`, `schemas/usuario.py`, `models/usuario.py`

**Endpoints:** `POST /auth/registro 201/409/422`, `POST /auth/login → Token`, `POST /auth/login/form` OAuth2, `GET /auth/me`

**Criterios:**
- [x] registro→login→JWT válido
- [x] ruta protegida 401 sin/inválido

---

### Issue 4 — Backend #1 (FastAPI): subida de video y disparo de Job — ✅ Completado

**Archivos:** `backend_fastapi/app/routers/videos.py`, `routers/jobs.py` `BackgroundTasks.add_task(_run_job)`

**Criterios:**
- [x] No bloquea request (202 antes de FFmpeg)
- [x] `pending→processing→completed/failed` polling 2s
- [x] Rechazo formato inválido con mensaje claro

---

### Issue 5 — Backend #1 (FastAPI): CRUD de Clips — ✅ Completado

**Archivos:** `routers/clips.py`, `schemas/clip.py`, `models/clip.py`

**Criterios:**
- [x] CRUD crear (vía Job) → listar → editar metadata → eliminar
- [x] 403/404 si clip de otro usuario
- [x] descarga `FileResponse` + dummy si storage vacío

---

### Issue 6 — Backend #2 (Express): paridad completa con FastAPI — ⚠️ Parcial → ✅ ~90% tras Issue 30

**Descripción:** Reimplementar mismos endpoints/contratos contra misma DB.

**Estado actualizado tras Issues 21/30:** `backend_express/src/app.ts` + `routes/auth|videos|jobs|clips|export|metrics|stats|users|publish`, `db/index.ts` (Pool normaliza `postgresql+psycopg2://`), `middleware/auth.ts` OK. Swagger `/docs` implementado (#50). Restan pulidos `retrim`/`stream` y `Dockerfile` entry en compose (parcial).

**Dependencias:** 3,4,5.

---

### Issue 7 — Frontend #1 (React): auth, subida y seguimiento de Jobs — ✅ Completado

**Archivos:** `frontend_react/src/pages/AuthPage.tsx`, `pages/UploadPage.tsx` `dropzone-neon`, `pages/JobStatusPage.tsx`, `context/AuthContext.tsx`, `hooks/useJobPolling.ts` 2000ms

**Criterios:**
- [x] flujo registro→login→subir→ver status sin reload
- [x] validación muestra errores claros

---

### Issue 8 — Frontend #1 (React): gestión y publicación de Clips — ✅ Completado vía Issue 28

**Estado:** Biblioteca completa con toolbar 1 fila (Issue 18), Dashboard recharts, Settings. Modal Publicar cableado en **Issue 27/28** (`POST /clips/{id}/publicar`).

**Archivos:** `pages/ClipLibraryPage.tsx`, `components/ExportDropdown.tsx`, `pages/DashboardPage.tsx`

**Criterios:**
- [x] Listar con filtros y paginación
- [x] Editar/borrar/publicar desde UI (Issue 28)

---

### Issue 9 — Frontend #2 (Vue): paridad completa con React — ✅ Completado

**Archivos:** `frontend_vue/src/views/AuthView.vue`, `UploadView.vue`, `JobStatusView.vue`, `DashboardView.vue`, `ClipLibraryView.vue`, `stores/auth.ts` Pinia, `composables/useJobPolling.ts`, `api/client.ts`

**Criterios:**
- [x] Mismo flujo y vistas contra mismo backend

---

### Issue 10 — Feature: subtitulado automático (burned-in) — ✅ Completado vía Issue 29

**Descripción:** Subtítulos quemados palabra por palabra via FFmpeg.

**Implementado Issue 29 (#49):** `backend_fastapi/app/services/ass_generator.py` `generate_hooked_ass` PlayRes 1080x1920 + `services/ffmpeg_service.py` `burn_subtitles` `ass=` + `jobs.py:_render_clip_with_ass_and_hook`. Degradación a `cut` si Whisper/FFmpeg falla, tags `_render`.

**Criterios:**
- [x] Cada clip incluye subtítulos legibles sincronizados (validado `test_issue_29_pipeline.py` `ffprobe 720x1280` + `burn` 23MB)

**Dependencias:** 2,5.

---

### Issue 11 — Feature: generación de hook inicial — ✅ Completado vía Issue 29

**Descripción:** Detectar fragmento mayor energía y anteponer al inicio del clip.

**Implementado Issue 29 (#49):** `services/hook_service.py` `detect_hooks` LLM + fallback `_mock_hooks` + `ffmpeg_service.build_hook_clip` `hook 3-6s` dentro `clip 15-60s` + `ass_generator.generate_hooked_ass` shift `0→hook_dur` + `hook_dur→hook_dur+clip_dur`.

**Criterios:**
- [x] Clip arranca con segmento hook
- [x] Hook score > promedio clip (viral_score 80-100)

---

### Issue 12 — Feature: subida automática a redes sociales — ✅ Completado vía Issues 27/28

**Descripción:** `POST /clips/{id}/publicar` → subida async → `publication_status=published`.

**Implementado Issues 27 (#47) + 28 (#48):** `routers/publish.py` + `services/publish_service.py` + `services/tiktok|youtube|instagram_service.py` + UI `ClipLibraryPage` modal Publish.

**Criterios:**
- [x] Endpoint publica y guarda link
- [x] UI refleja `publicado`

---

### Issue 13 — Seguridad y empaquetado final — ⚠️ Parcial

**Descripción:** Eliminar secretos hardcodeados y completar `docker-compose.yml`.

**Estado:** JWT/bcrypt OK. Pendiente rotar `ANTHROPIC_API_KEY` `sk-ant-api03-...` en git history `BFG` y `requirements.txt` `bcrypt==4.1.2`, `backend_express/Dockerfile`. Compose ahora con `db + backend_fastapi + backend_express` OK, frontends `preview` pendiente Issues 31–35.

**Acción:** ver Issue 35 (deuda técnica UI).

---

### Issue 14 — Documentación de API (OpenAPI/Swagger) — ✅ Completado

**Descripción:** Spec OpenAPI en ambos backends.

**Estado:** FastAPI `/docs` + `/redoc` + `/openapi.json` auto-generado Pydantic. Express **Issue 30 (#50)** `GET /docs` Swagger UI + `GET /openapi.json` `ClipsAI Express API 1.0.0` `backend_express/src/docs/swagger.ts` + `JSDoc @openapi` en `app.ts:/health`.

**Archivos:** `backend_fastapi/app/main.py` (`ClipsAI 1.0.0`), `backend_express/src/docs/swagger.ts`, `backend_express/src/app.ts` `swaggerUi.serve`.

**Criterios:**
- [x] FastAPI `/docs` actualizada
- [x] Express `/docs` con todos los endpoints (`openapi 3.0.0` 18 paths, `title ClipsAI Express API`)

---

## Issues 15–22 — Actualizados (Propuestas → Ejecución)

### Issue 15 — Completar paridad Express (auth + videos + jobs + CRUD clips) — ✅ Completado vía Issue 21/30

**Descripción:** Llevar Express de 35% → 100% paridad.

**Implementado:** `src/routes/auth.ts` `POST /auth/registro 201/409`, `POST /auth/login`, `GET /auth/me`, `src/routes/videos.ts` `multer` 500MB, `src/routes/jobs.ts` `POST /videos/:id/jobs 202 + setImmediate`, `routes/clips.ts` `video_id/status` + `GET/PATCH/DELETE /clips/:id`.

---

### Issue 16 — Wirear motor real en FastAPI — ✅ Completado vía Issue 21

**Implementado Issue 21 (#36):** `backend_fastapi/app/services/engine.py` `from engine import procesar_video` real + `Dockerfile` `ffmpeg` + `storage/clips/{job_id}/` + `ProcesamientoResultado.error_tipo` → `job.error_message`.

---

### Issue 17 — Rediseño Cyber-Tech Dark Mode unificado — ✅ Completado (Nov 2026) — equiv. #34 Spark Admin

**Implementado:** `frontend_react/src/styles/spark.css` + `frontend_vue/src/assets/spark.css` `:root` `--bg-app:#0B0F17` `--brand-lime:#B4F105` etc. — **PR #34** Spark Admin.

---

### Issue 18 — Refactor Biblioteca filtros a toolbar compacta 1 fila — ✅ Completado (Nov 2026)

**Implementado:** `ClipLibraryPage.tsx` + `LibraryPage.tsx` + `ClipLibraryView.vue` toolbar `56px` `flex p-3 bg-[#121824]`.

---

### Issue 19 — Implementar subtítulos burned-in + hook reordering — ✅ Completado vía Issue 29

**Cerrado por Issue 29 (#49):** ver Issues 10/11.

---

### Issue 20 — Publicación automática a redes + UI — ✅ Completado vía Issues 27/28

**Cerrado por Issues 27 (#47) + 28 (#48):** ver Issue 12.

---

### Issue 21 — Cableado del Pipeline Backend, Engine de Renderizado y Routers FastAPI — ✅ Completado (#36)

**PR:** #36 — **Issue #21**

**Descripción:** Cerrar Issue 13 parcialmente conectando engine real.

**Alcance:** `backend_fastapi/app/services/engine.py` real, `routers/jobs.py` `jobs._run_job` con `storage/clips`, `Dockerfile` `ffmpeg`, `ASSESS` `ENGINE_MODE=real`.

**Evidencias:** `ffprobe duration 30-90s`, `JobStatusPage` sin `Modo simulado`, `POST /videos/{id}/jobs` genera `.mp4` real.

---

### Issue 22 — Esquema de Base de Datos para Cuentas Sociales — ✅ Completado (#42)

**PR:** #42 — **Issue #22**

**Descripción:** Tabla `social_accounts` / `user_social_accounts` para OAuth.

**Archivos:** `init-scripts/02-social-accounts.sql` + `backend_fastapi/app/models/social_account.py` + `ALTER TABLE social_accounts ADD COLUMN account_name`.

**Evidencias:** `psql \d social_accounts` FK `user_id → usuarios` CASCADE.

---

## Issues 23–30 — Completadas (Cerradas en GitHub)

### Issue 23 — Configuración de Túnel HTTPS Local (ngrok & Callbacks) — ✅ Completado (#43)

**PR:** #43 — **Issue #23**

**Descripción:** Exponer `backend_fastapi:8000` y `backend_express:3001` vía ngrok/Cloudflare Tunnel `https://api.clipsai.xyz` para callbacks OAuth.

**Archivos:** `docker-compose.yml` `ngrok` service `backend_fastapi:8000 --domain=api.clipsai.xyz`, `backend_fastapi/app/config.py` `PUBLIC_BACKEND_URL`.

**Evidencias:** `curl https://api.clipsai.xyz/health` `{"status":"ok"}` + `ngrok inspect http://localhost:4040`.

---

### Issue 24 — Flujo OAuth 2.0: Conector de YouTube (Google Data API v3) — ✅ Completado (#44)

**PR:** #44 — **Issue #24**

**Archivos:** `backend_fastapi/app/routers/social_auth.py` `GET /auth/social/youtube` + `/callback`, `services/youtube_service.py`, `GOOGLE_CLIENT_ID/SECRET`.

**Evidencias:** `GET /auth/social/youtube` redirect Google + token guardado en `social_accounts` + `POST /clips/{id}/publicar youtube` `PUBLISHED`.

---

### Issue 25 — Flujo OAuth 2.0: Conector de Meta (Instagram Graph API) — ✅ Completado (#45)

**PR:** #45 — **Issue #25**

**Archivos:** `backend_fastapi/app/routers/social_auth.py` `instagram`, `services/instagram_service.py` `graph.facebook.com/v18.0/{ig_user_id}/media` + `media_publish`.

**Evidencias:** Instagram Business `19.0` container polling `FINISHED` → `https://www.instagram.com/reel/{id}`.

---

### Issue 26 — Flujo OAuth 2.0: Conector de TikTok (Content Posting API) — ✅ Completado (#46)

**PR:** #46 — **Issue #26**

**Archivos:** `backend_fastapi/app/services/tiktok_service.py` `open.tiktokapis.com/v2/post/publish/video/init` `FILE_UPLOAD` `PUT upload_url`.

**Evidencias:** `publish_id` + `upload_url` + `PUT` `200` → `https://www.tiktok.com/@{user}/video/{publish_id}`.

---

### Issue 27 — Servicio de Publicación Real en APIs de Redes Sociales — ✅ Completado (#47)

**PR:** #47 — **Issue #27**

**Archivos:** `backend_fastapi/app/services/publish_service.py` `publish_clip_task` + `TIKTOK_CLIENT_KEY/SECRET` `FACEBOOK_CLIENT_ID/SECRET` + `BackgroundTasks`.

**Evidencias:** `POST /clips/{id}/publicar {platform,caption}` `202 PUBLISHING` → `PUBLISHED` + `social_post_url`.

---

### Issue 28 — Vista de Gestión de Integraciones (/settings/integrations) — ✅ Completado (#48)

**PR:** #48 — **Issue #28**

**Archivos:** `frontend_react/src/pages/SettingsPage.tsx` + `frontend_vue/src/views/SettingsView.vue` `/settings/integrations` OAuth connect/disconnect + `Avatar 56px` + `ProfileMenu`.

**Evidencias:** `GET /settings/integrations` lista YouTube/Instagram/TikTok con badge `Conectado` + `Ver post`.

---

### Issue 29 — Integración de Subtítulos ASS y Hook Teaser en Pipeline FFmpeg — ✅ Completado (#49)

**PR:** #49 — **Issue #29**

**Descripción:** Conectar `ass_generator` y `hook_service` al `jobs._run_job`.

**Archivos:** `backend_fastapi/app/routers/jobs.py` `_render_clip_with_ass_and_hook` + `services/ass_generator.py` `generate_hooked_ass` + `services/ffmpeg_service.py` `burn_subtitles/build_hook_clip/cut_segment` + `services/hook_service.py` `detect_hooks` + `services/whisper_service.py` + `Dockerfile` `ffmpeg`.

**Evidencias:** `test_issue_29_pipeline.py` 12/12 PASS `ffmpeg 8.1` + `ASS PlayRes 1080x1920` shift `hook 0→5s` + `render hook+ass` 23MB `ffprobe 720x1280 9:16` + fallback `tags["_render_error"]` + `COMPLETED`.

---

### Issue 30 — Swagger / OpenAPI 3.0 para Backend Express — ✅ Completado (#50)

**PR:** #50 — **Issue #30**

**Archivos:** `backend_express/src/docs/swagger.ts` `openapi 3.0.0` `title ClipsAI Express API 1.0.0` `apis: ['./src/routes/*.ts','./src/controllers/*.ts']` + `backend_express/src/app.ts` `app.use('/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec))` + `GET /openapi.json` + `JSDoc @openapi` en `app.ts:/health`.

**Dependencias:** `swagger-ui-express@5.0.1` `swagger-jsdoc@6.3.0` + `@types`.

**Evidencias:** `npm run typecheck` `EXIT:0`, `curl /health 200`, `curl /docs 200 swagger-ui`, `curl /openapi.json` `14554 bytes` `paths 18`.

---

## Issues 31–35 — Pendientes (Abiertas en GitHub #51–#55)

### Issue 31 — Eventos en Tiempo Real (SSE) para Estado de Publicación — ⏳ Pendiente (#51)

**Descripción:** Notificar al frontend sin polling 2s: `GET /clips/{id}/stream` SSE o WebSocket para `PUBLISHING→PUBLISHED`.

**Alcance:** `backend_fastapi/app/routers/stream.py` SSE + `backend_express/src/routes/stream.ts` + `frontend_react/src/hooks/usePublishPolling.ts` 1s + `frontend_vue` composable.

**Dependencias:** 27, 28.

**Criterios:**
- [ ] `curl /clips/{id}/stream` SSE `data: {"status":"PUBLISHED"}`
- [ ] UI badge cambia `PUBLISHING→PUBLISHED` sin reload + link `social_post_url`

---

### Issue 32 — Landing Page Pública e Index (/) — ⏳ Pendiente (#52)

**Descripción:** Crear `/` pública SEO sin auth con hero, features, pricing, CTA `→ /auth`.

**Archivos:** `frontend_react/src/pages/LandingPage.tsx` + `frontend_vue/src/views/LandingView.vue` + `router/index.ts` `/` public.

**Criterios:**
- [ ] `GET /` sin auth renderiza hero + features + CTA
- [ ] `npm run build` + `lighthouse` SEO ≥90

---

### Issue 33 — Páginas Legales para Validación de APIs (/privacy, /terms, /data-deletion) — ⏳ Pendiente (#53)

**Descripción:** Requerido para validación Meta/Google/TikTok: privacy policy, términos y data deletion.

**Archivos:** `frontend_react/src/pages/PrivacyPage.tsx` `/privacy`, `TermsPage.tsx` `/terms`, `DataDeletionPage.tsx` `/data-deletion` (Vue idem).

**Criterios:**
- [ ] `GET /privacy` `200` con política + contacto
- [ ] `GET /terms` `200` + `GET /data-deletion` instrucciones borrado
- [ ] Enlace en footer `Layout.tsx` + `Layout.vue`

---

### Issue 34 — Modo "Video de Muestra" en Pantalla de Carga (/upload) — ⏳ Pendiente (#54)

**Descripción:** Permitir probar el flujo sin subir video propio: botón `Probar con video de muestra` usa `river.mp4` + transcripción fixture.

**Archivos:** `frontend_react/src/pages/UploadPage.tsx` `sample_test.mp4` + `backend_fastapi/app/routers/videos.py` `POST /videos/sample`.

**Criterios:**
- [ ] `POST /videos/sample` `201` sin `multipart` + `POST /videos/{id}/jobs 202` → clips visibles
- [ ] UI botón `Video de muestra` + badge `Muestra`

---

### Issue 35 — Refactorización y Limpieza de Deuda Técnica en UI — ⏳ Pendiente (#55)

**Descripción:** Eliminar duplicados `LibraryPage==ClipLibraryPage` (4 ficheros), `axios` muerto en React, `useUploadAndProcess` muerto, `passlib[bcrypt]` muerto, `recharts` vs CSS barras, `any` en `Clip.tags`.

**Archivos:** `frontend_react/src/pages/LibraryPage.tsx` (eliminar), `frontend_vue/src/views/LibraryView.vue` (eliminar), `backend_fastapi/requirements.txt`, `backend_fastapi/app/models/clip.py` `tags: dict`.

**Criterios:**
- [ ] `git grep -r "LibraryPage"` solo 2 archivos (no 4)
- [ ] `npm run typecheck` + `npm run build` ambos frontends verde
- [ ] `pytest -q` + `tsc --noEmit` verde

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
- Webhooks `POST /webhooks/job-completed` para notificar frontend via SSE/WebSocket en vez de polling 2s → Issue 31
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
        │                    │                        ├─→ 8 (React clips) ─→ 28 (Integraciones)
        └─→ 2 (Engine) ──────┘                        └─→ 7 (React upload) ─→ 9 (Vue)
                                                      10 (subs) ─┐
                                                      11 (hook) ─┤→ 21 (pipeline) ─→ 29 (ASS+Hook) ─→ 27 (publish real)
                                                        17 (dark) ─→ 18 (toolbar) ─┐
                                                        22 (DB social) ─→ 23 (ngrok) ─→ 24 (YouTube) ─→ 25 (Instagram) ─→ 26 (TikTok) ─→ 27 ─→ 28
                                                        30 (Swagger Express) ─→ 31 (SSE) ─→ 32 (Landing) ─→ 33 (Legales) ─→ 34 (Muestra) ─→ 35 (Deuda UI)
```

**Rama activa sugerida para próximos:** `feat/sse-publish` (Issue 31) o `feat/landing-publica` (Issue 32).
