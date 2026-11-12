# Issues de calidad — Hallazgos de la auditoría de noviembre 2026

> Documento de seguimiento: los hallazgos de calidad detectados durante la rama
> `fix/quality-audit-score` que quedaron **fuera del alcance** de esta rama.
> Listos para pasar a GitHub Issues con `gh issue create` (comandos al final).

---

## Fase 4 — DBG 0, Coh 0 y reducción de complejidad (12-nov, rama `fix/quality-index-100`)

### Resultado

| Señal | Antes | Después |
|---|---|---|
| **DBG** | 14 (`backend_express/src/routes/jobs.ts`, `video_processor.py`) | **0** — `jobs.ts` usa `src/lib/logger.ts` (sin `console.*`, salida por `process.stdout/stderr`); `video_processor.py` usa `logging` |
| **Coh** | 1 (`editor_viral.py`) | **0** — atributos compat muertos fuera, `verificar_ffmpeg`/`sondear_dimensiones` → funciones de módulo, métodos de la fachada comparten el mismo eje de estado |
| **Compl** | 282 bloques (informe cátedra) | **~151 estimados** (medición local; máx CC por función **193 → 27**) |

Verificación: `python -m pytest -q --cov=app --cov=backend --cov=backend_fastapi.app` →
**626 passed, 81 %** · `npm run typecheck` + `npm run build` (backend_express) → exit 0.

### Funciones divididas (todas con suite verde)

`_run_job` 193 · `run_clip_engine` 96 · `_run_re_render` 75 · `_refresh_account_token` 60 ·
`publish_clip_task` 59 · `_publish_tiktok` 48 · `procesar_video` 47 · `_call_anthropic_with_model` 43 ·
`_publish_instagram` 40 · `obtener_clips_ia` 32 · `run_subtitle_pipeline` 31 · `upload_video` 30 ·
`transcribe_wav` 29 · `generate_ass_from_segments` 27 · `_parse_and_validate` 27 ·
`_fetch_instagram_username` 27 · `retrim_clip` 26 · `_publish_youtube` 25.

### Restante para llegar a <133 bloques (si la métrica de la cátedra lo exige)

- Tier medio Python (CC 20-27): `process_video_job` (backend/handler.py), `_normalize_transcription_segments`,
  `select_clips_via_claude`, `save_instagram_tokens`, `main()` (main.py), `score()` (track_b),
  `reframe_video`, `parsear_transcripcion_youtube`, `download_clip`, `publish_stream`/`event_gen`.
- Archivos TS con más ramas: `routes/clips.ts` (~210), `routes/socialAuth.ts` (~141),
  `routes/jobs.ts` (~124), `routes/subtitles.ts` (~116) — extraer helpers por endpoint.

### Script de medición (calibración)

```python
# medir_cc.py — complejidad ciclomática del repo (no commitear)
# Python: AST con If/For/While/ExceptHandler/BoolOp/comprensiones/Match, umbral CC>8 por función.
# TS/TSX: regex de ramas (if/else if/for/while/case/catch/&&/||/??/ternarios) por archivo.
# Calibración: la cifra de la cátedra (282 sobre main del 11-nov) ≈ py CC>7 + bloques TS por función.
```

---

## Issue 1 — Optimizar llamadas HTTP sincrónicas a Meta dentro de la publicación (Instagram)

**Problema:** Dentro del flujo de publicación hay funciones que golpean la API de Meta/Dominio
público **en cada publicación**, de forma sincrónica y sin cache:

- `backend_fastapi/app/services/publish_service.py::_get_ngrok_domain()` — consulta HTTP para
  resolver el dominio del túnel público en cada intento de publicación.
- `backend_fastapi/app/services/publish_service.py::_resolve_instagram_business_id(account)` —
  llama `POST graph.facebook.com/v18.0/me/accounts` **en cada intento**, sin cache persistente.

**Impacto:** minutos de latencia en la publicación de Instagram; un túnel lento o una respuesta
de Meta con error rompe o ralentiza el flujo (ver evidencia del auditor: los tests tuvieron
que mockear ambas funciones en `test_publish_service_coverage.py`, con los logs de la API de
Meta en consola).

**Qué hacer:**
1. Cachear `_get_ngrok_domain()` en nivel módulo con TTL de ~5 min (usa `PUBLIC_BACKEND_URL` como primer valor evitando la llamada).
2. Guardar el `ig_user_id` resuelto al momento de la conexión OAuth en `social_accounts` (campo `platform_account_id` ya existe) y usarlo como primera lectura — solo re-resolver si falla.
3. Bajar timeouts del fallback (3 s) y agregar un `try/except` que acompañe el fallback directo del dominio público.

**Criterio de cierre:** `publish_clip_task("instagram")` con cuenta conectada no emite ninguna
request GET a `graph.facebook.com` antes del POST de creación del contenedor.

---

## Issue 2 — Agregar `backend_express/dist/` a `.gitignore`

**Problema:** `backend_express/dist/` está versionado. Cada vez que se corre `npm run build`
(o `npm run audit`, que lo ejecuta), recompilar regenera los archivos y aparecen diffs completos
por cambios de finales de línea (LF/CRLF según `.gitattributes`), contaminando los commits con
ruido tipo `warning: LF will be replaced by CRLF` y diffs sin contenido real.

**Qué hacer:**
1. Agregar `backend_express/dist/` a `.gitignore`.
2. `git rm -r --cached backend_express/dist/` (deja de versionarlo, mantiene el build local).
3. Confirmar que `backend_express/scripts/fastapi-routes.json` (snapshot de auditoría) sigue versionado y accesible sin dist.

**Criterio de cierre:** `npm run audit` completo regenerable y `git status` limpio posterior.

---

## Issue 3 — Segunda fase de cobertura (pipeline real: FFmpeg/Whisper/RunPod) — ✅ CERRADA (Fase 3)

> **Estado 11-nov-2026:** cerrada por la Fase 3 en `feat/quality-perfection-phase3`.
> Suite final: **626 tests**, cobertura global **80,3 %** (era 69 % tras la Fase 2 y 18 % en el
> informe original de la cátedra). Ver evidencia al final de esta sección.

**Problema:** Después de subir la cobertura del backend de 15% a 64% (commit `f1413d4`
de esta rama), quedan sin cubrir los módulos que **ejecutan el pipeline real**. Mockearlos
a fondo (subprocess/HTTP) requiere tests más verbosos, pero son los últimos sumideros.

| Archivo | Stmts sin cubrir | Qué es |
|---|---|---|
| `app/services/engine.py` | 245 | `run_clip_engine()`: delegación RunPod vs. local, callbacks de progreso |
| `app/services/whisper_service.py` | 162 | Whisper local (GPU/temperature), craft de extract_wav y transcripción |
| `app/tasks/subtitle_pipeline.py` | 151 | pipeline ASS/burn/whisper para un clip a pedido |
| `app/routers/jobs.py` (ramas restantes) | 382 | restos de `_run_job` (resiliencia, fallos pyparse parciales) |
| `app/services/publish_service.py` (resto) | 314 | `_refresh` Instagram + webhooks retries |
| `app/main.py` | 104 | lifespan completo (migración con SQLAlchemy activo) |
| `app/services/runpod_service.py` | 89 | polling de `runsync` con timeouts/retries |

**Qué hacer:** suite adicional con mocks profundos de subprocess/HTTP por rama. Estimación:
se pueden cubrir ~1.000 de esos ~1.600 stmts con ~40 tests, llevando la cobertura global del
backend al **75-80%** exigido por la cátedra (`docs/EVALUACION.md`).

**Evidencia de cierre (11-nov-2026, rama `feat/quality-perfection-phase3`):**

```
python -m pytest -q --cov=app --cov=backend --cov=backend_fastapi.app
# 626 passed · TOTAL 8295 stmts · 1636 miss · 80% (80,27 % exacto)
```

| Módulo | Antes (Fase 2) | Después (Fase 3) | Tests nuevos |
|---|---|---|---|
| `app/routers/jobs.py` | 59 % (382 miss) | **87 %** (111 miss) | `test_phase3_jobs.py` (42) + `test_phase3_remate.py` |
| `app/services/publish_service.py` | 58 % (314) | **92 %** (58) | `test_phase3_publish.py` (87) |
| `app/main.py` (lifespan) | 47 % (104) | **86 %** (27) | `test_phase3_runpod_main.py` + `test_phase3_remate.py` |
| `app/services/runpod_service.py` | 57 % (89) | **98 %** (4) | `test_phase3_runpod_main.py` (47) |
| `app/cli.py` | 0 % (130) | **99 %** | `test_phase3_retrim_stream_cli.py` (34) |
| `backend/api/routes/retrim.py` + `stream.py` | 27/35 % | **90/97 %** | idem |
| `app/database.py`, `deps.py`, `_clip_common.py` | 65/91/78 % | 95/100/100 % | `test_phase3_small_gaps.py` (14) |

Extras de calidad en el mismo PR:
- **Código muerto eliminado** en `app/routers/jobs.py`: la primera definición de
  `run_job_safely` (sombrada por la segunda, ~40 líneas inalcanzables) y el `raise`
  inalcanzable tras el `try/finally` de `_render_clip_with_ass_and_hook`.
- Las ramas restantes sin cubrir son, en su mayoría, `except Exception: pass` de
  logging/flush y el bloque de import-time de `main.py` (resolución de raíz), no
  comportamiento de negocio.

---

## Hallazgos adicionales (documentación para revisión)

- Confirmado por lectura de código + tests: el `except` global de `_run_job` (`jobs.py`)
  **no re-lanza**: marca el job `FAILED` con mensaje descriptivo y termina. Solo la rama de
  error de Claude re-lanza (y el wrapper la captura). Documentado en
  `backend_fastapi/tests/test_jobs_heavy_coverage.py`.
- `backend/services/*` y `backend/track_*/*` contienen copias divergentes
  (gemelos con comportamiento distinto, p. ej. `MockPublisher` con salidas diferentes).
  Conviene reactivar la deduplicación de la Issue 42 (`ISSUES.md`) para esos módulos.
- Se agregó `.coverage`/`htmlcov/` al `.gitignore` para acumular artefactos de cobertura off
  git.

### Comandos de referencia

```bash
# cobertura global (core + backend + fastapi)
python -m pytest -q -p no:cacheprovider --cov=app --cov=backend --cov=backend_fastapi.app --cov-report=term
# cobertura literal del pedido
python -m pytest -q -p no:cacheprovider --cov=app --cov=backend_fastapi/app --cov-report=term-missing
# crear las issues en GitHub (después de pushear)
gh issue create -t "fix(publish): cachear dominio público e ig_user_id en la publicación" \
  -b "Ver 'Issue 1' en ISSUES_CALIDAD_PENDIENTES.md"
gh issue create -t "chore(git): ignorar backend_express/dist y dejar de versionarlo" \
  -b "Ver 'Issue 2' en ISSUES_CALIDAD_PENDIENTES.md"
gh issue create -t "test(quality): fase 2 — cobertura del pipeline real (engine/whisper/subtitles)" \
  -b "Ver 'Issue 3' en ISSUES_CALIDAD_PENDIENTES.md"
```
