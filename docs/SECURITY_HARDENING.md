# Hardening de seguridad (ASH) — estado y acciones manuales

Este documento registra la pasada de seguridad solicitada por el equipo, por fuera
de las issues funcionales. Sigue la compuerta **ASH** de `project-quality-audit`:
primero secretos/acceso, después datos/red, por último dependencias y logging.

> No contiene valores de secretos, tokens ni credenciales. Los hallazgos se reportan
> por archivo/área y las claves expuestas deben rotarse fuera del repositorio.

## 1. Resumen

| Área | Antes | Después |
| --- | --- | --- |
| Cabeceras HTTP | Sin HSTS/CSP/XCTO/XFO | Middleware con HSTS, CSP, XCTO, XFO, Referrer-Policy, Permissions-Policy, COOP |
| CORS | `*` de Vercel/ngrok + credenciales | Allowlist exacta + `*.clipsai.xyz`; credenciales permitidas solo para cookies |
| Rate limit | Solo auth y videos | Límite global por IP + límites existentes; 429 con `Retry-After` |
| Host header | Sin validación | `TrustedHostMiddleware` con lista configurable |
| Sesión web | JWT en `localStorage` | Cookie `HttpOnly; Secure; SameSite`; logout; revocación por `token_version` |
| SSE | JWT en query (`?token=`) | Cookie de sesión (`EventSource withCredentials`); sin token en URL |
| CSRF | N/A con Bearer | Validación de `Origin`/`Referer` cuando hay cookie de sesión |
| Uploads | Extensión y tamaño | Magic bytes de MP4/MOV/AVI + texto sin NUL; tamaño y UUID |
| Logs OAuth | Respuestas crudas con tokens | Filtro de redacción + logs reducidos en origen |
| Descarga de clips | Pública por UUID | Firma HMAC de corta duración o auth/ownership; públicos solo publicados |
| Webhooks RunPod | HMAC sin idempotencia | HMAC + rechazo de callbacks terminales duplicados |
| JWT | python-jose 3.3.0 | PyJWT 2.15.1; algoritmo restringido a HS256/384/512; exp 8 h |
| Revocación | Token válido hasta expirar | `token_version` invalida sesiones al cambiar contraseña |
| Password hashing | bcrypt default | bcrypt explícito rounds=12 |
| DB runtime | Usuario owner/superusuario | Rol `clipsai_app` con DML mínimo; DDL con owner |
| Validación | Algunos schemas laxos | `extra="forbid"` en auth/perfil/clips/publicación |
| Dependencias Python | 40 vulns en 6 paquetes | `pip-audit` backend: **0**; root: **0**; worker: **0** |
| Dependencias frontend | 2 high, 4 moderate | `npm audit`: **0** (Vite 8, plugin-react 6, react-router 7) |
| Frontend headers | Sin CSP/HSTS | `vercel.json` y `nginx.conf` con CSP, HSTS y headers |
| CI | Solo build del worker | Workflow `Security` + Dependabot |
| Errores HTTP | Detalles crudos | Redacción de tokens + 500 genérico sin stack traces |

## 2. Cambios de código

- `backend_fastapi/app/core/logging_security.py`: `RedactionFilter` y `redact()` para
  access/refresh tokens, `Bearer`, claves `sk-ant`, `AKIA`, `ghp_`, `AIza`.
- `backend_fastapi/app/core/security_middleware.py`: request ID, rate limit global,
  límite de body JSON, cabeceras de seguridad, CSRF por Origin y logging de 401/403/429/5xx.
- `backend_fastapi/app/core/session.py`: cookie HttpOnly, flags y helpers set/clear.
- `backend_fastapi/app/core/cors.py`: allowlist/regex compartidos entre app y CSRF.
- `backend_fastapi/app/main.py`: CORS con credenciales, TrustedHost, handlers de
  excepción con redacción y error 500 genérico.
- `backend_fastapi/app/routers/auth.py`: cookie de sesión en login; `POST /auth/logout`.
- `backend_fastapi/app/deps.py`: auth por cookie o Bearer; validación de `token_version`.
- `backend_fastapi/app/routers/stream.py`: SSE autenticado por cookie/Bearer, sin query token.
- `backend_fastapi/app/routers/users.py`: cambio de contraseña incrementa `token_version`
  y emite cookie nueva.
- `backend_fastapi/app/models/usuario.py` + migración: columna `token_version`.
- `backend_fastapi/app/routers/videos.py`: validación de magic bytes antes de escribir.
- `backend_fastapi/app/routers/clips.py`: descarga con firma o auth/ownership.
- `backend_fastapi/app/services/media_signing.py`: URLs firmadas HMAC con TTL.
- `backend_fastapi/app/routers/webhooks.py`: idempotencia de callbacks.
- `backend_fastapi/app/security/jwt.py`: PyJWT + claim `ver`.
- `backend_fastapi/app/config.py`: algoritmo JWT restringido, exp 480 min,
  `APP_DATABASE_URL`.
- `backend_fastapi/app/security/hashing.py`: bcrypt rounds=12 explícito.
- `backend_fastapi/app/database.py`: engine runtime con rol limitado;
  `migration_engine` owner para DDL.
- `init-scripts/03-app-role.sh` + `docker-compose.yml`: rol `clipsai_app` con
  `SELECT/INSERT/UPDATE/DELETE`; DDL sigue con `POSTGRES_USER`.
- `backend_fastapi/app/services/publish_service.py` y `instagram_service.py`/
  `tiktok_service.py`/`youtube_service.py`: logs OAuth sin cuerpos crudos.
- `frontend_react/src/lib/apiClient.ts`: sin `localStorage`; `credentials: 'include'`.
- `frontend_react/src/components/auth/AuthProvider.tsx` + `context/AuthContext.tsx`:
  sesión por cookie; logout contra `/auth/logout`.
- `frontend_react/src/hooks/usePublishSSE.ts`: `EventSource` con `withCredentials`.
- `frontend_react/src/hooks/useIntegrations.ts` y `services/api.ts`: sin Bearer manual.
- `frontend_react/vercel.json` + `frontend_react/nginx.conf`: CSP/HSTS/headers.
- `frontend_react/package.json` + lockfiles: Vite 8.4, `@vitejs/plugin-react` 6.3,
  `react-router-dom` 7.18.7; `npm audit` 0.
- `.github/workflows/security.yml` + `.github/dependabot.yml`: tests de seguridad,
  `pip-audit`, `npm audit`, build y gitleaks (señal no bloqueante).
- `backend_fastapi/requirements-test.txt`: dependencias mínimas para CI.
- `backend_fastapi/requirements.txt`: FastAPI 0.165, Starlette 1.10, PyJWT, multipart,
  requests y dotenv parcheados.

## 3. Acciones manuales obligatorias

Estas acciones no se pueden completar solo con el código:

1. **Rotar claves expuestas en el historial.** El historial contiene material de claves
   (proveedor Anthropic y AWS). Rotar/revocar esas claves y, si el repo se considera
   comprometido, limpiar el historial con `git filter-repo`/BFG y coordinar el force
   push. No se imprime ningún valor. El job `secrets-history` queda como señal hasta
   completar esta acción.
2. **Configurar el hosting** con:
   - `JWT_SECRET` fuerte y `JWT_ALGORITHM=HS256`.
   - `VAULT_KEY` de 32 bytes persistente.
   - `STORAGE_SIGN_KEY` fuerte (o asumir el fallback a `JWT_SECRET`).
   - `RUNPOD_WEBHOOK_SECRET` obligatorio en producción.
   - `ALLOWED_HOSTS`, `CORS_ORIGIN_REGEX` y `SECURITY_RATE_LIMIT` según el dominio.
   - `SESSION_COOKIE_NAME`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE`,
     `SESSION_COOKIE_DOMAIN` según el despliegue.
   - `APP_DATABASE_URL` con el rol de runtime y `DATABASE_URL` con el owner.
   - `APP_ENV=production`.
3. **HTTPS/HSTS** en Vercel/Render/Cloudflare. Verificar con `curl -I` que HSTS,
   CSP, XCTO, XFO y Referrer-Policy estén presentes. La app confía en el proxy para
   HTTPS; no agregar un redirect interno que pueda generar loops.
4. **Base de datos:** el compose nuevo crea `clipsai_app` en el primer arranque de un
   volumen vacío. Si la base ya existe, correr el equivalente de
   `init-scripts/03-app-role.sh` una vez como owner. El backend usa
   `APP_DATABASE_URL` para DML y `DATABASE_URL` para DDL/migraciones.
   RLS de PostgREST/Supabase **no aplica** a este backend propio: el control de acceso
   es app-level (ownership por `user_id`) + ORM parametrizado. Si se adopta RLS, hacerlo
   con `SET LOCAL app.user_id` y políticas deny-by-default en una migración revisada.
5. **Probar en navegador real:** login con cookie, `/auth/me`, SSE de publicación,
   descarga de clip no publicado, OAuth y logout. En previews cross-site
   (Vercel/Render en dominios distintos) puede hacer falta
   `SESSION_COOKIE_SAMESITE=none` + `SESSION_COOKIE_SECURE=true`.
6. **CI:** el workflow `Security` corre tests acotados, `pip-audit`, `npm audit` y build.
   La suite completa tiene 13 fallos preexistentes de `main`; cuando se corrijan, ampliar
   el job a toda la suite con cobertura.
7. **Dependencias del worker:** `pip-audit -r requirements-worker.txt` dio **0**; Dependabot
   queda configurado para detectar regresiones de `mediapipe`/`litellm`/`faster-whisper`.

## 3.1 Riesgos aceptados / pendientes

- **Historial de claves:** sigue siendo el riesgo crítico hasta rotar/purgar.
- **Rate limit en memoria:** no se comparte entre réplicas. Para multi-instancia, usar
  Redis/Upstash.
- **CSP del frontend:** validada con build, no con navegador real. Verificar en producción
  que Google Fonts, Bootstrap Icons y las llamadas a la API no queden bloqueadas.
- **Errores de proveedores:** el handler global redacta tokens, pero algunos cuerpos de
  error de TikTok/Meta/YouTube todavía pueden incluir detalles del proveedor. Sanitizar
  en una próxima pasada si se quiere ocultar todo el cuerpo.
- **Password reset:** no existe flujo de recuperación; es **N/A** hasta que el producto
  lo defina (requiere tabla, email y tokens de un solo uso de 15–60 min).
- **RLS:** **N/A** para backend propio; el mínimo privilegio de DB sí quedó implementado.
- **Cobertura:** 79,4 % global; debajo de 80 por deuda preexistente, con los módulos
  nuevos entre 90 % y 100 %.

## 4. Verificación

```bash
# Backend
pytest backend_fastapi/tests -q --cov=backend_fastapi/app
pip-audit -r backend_fastapi/requirements.txt
pip-audit -r requirements-worker.txt

# Frontend
cd frontend_react
npm ci
npm run build
npm audit

# Cookie/CSRF/SSE (tests acotados)
pytest -q backend_fastapi/tests/test_security_hardening.py
pytest -q backend_fastapi/tests/test_routers_coverage.py::TestAuth
pytest -q backend_fastapi/tests/test_routers_coverage.py::TestPublishStream

# Headers (producción)
curl -sI https://clipsai.xyz/ | grep -Ei 'strict-transport|content-security|x-content-type|x-frame|referrer-policy'
curl -sI https://api.clipsai.xyz/health | grep -Ei 'strict-transport|content-security|x-content-type|x-frame|referrer-policy|x-request-id'
```

Resultado esperado en el repo: tests existentes en verde (salvo los 13 fallos
preexistentes de `main`), `pip-audit` 0 en backend/root/worker, `npm audit` 0 y build
Vite OK.

## 5. Nota de alcance

La compuerta ASH no cierra con este documento: la rotación de claves del historial, la
configuración del hosting, HTTPS/CSP en producción y la prueba de navegador siguen
siendo acciones manuales. El código y las pruebas quedan listos para verificarlas.
