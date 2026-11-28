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
| CORS | `*` de Vercel/ngrok + credenciales | Allowlist exacta + `*.clipsai.xyz`; sin credenciales; configurable por env |
| Rate limit | Solo auth y videos | Límite global por IP + límites existentes; 429 con `Retry-After` |
| Host header | Sin validación | `TrustedHostMiddleware` con lista configurable |
| Uploads | Extensión y tamaño | Magic bytes de MP4/MOV/AVI + texto sin NUL; tamaño y UUID |
| Logs OAuth | Respuestas crudas con tokens | Filtro de redacción + logs reducidos en origen |
| Descarga de clips | Pública por UUID | Firma HMAC de corta duración o auth/ownership; públicos solo publicados |
| Webhooks RunPod | HMAC sin idempotencia | HMAC + rechazo de callbacks terminales duplicados |
| JWT | python-jose 3.3.0 | PyJWT 2.15.1; algoritmo restringido a HS256/384/512; exp 8 h |
| Password hashing | bcrypt default | bcrypt explícito rounds=12 |
| Dependencias Python | 40 vulns en 6 paquetes | `pip-audit` backend: **0**; root: **0**; worker: **0** |
| Dependencias frontend | 2 high, 4 moderate | `npm audit`: **0** (Vite 8, plugin-react 6, react-router 7) |
| Frontend headers | Sin CSP/HSTS | `frontend_react/vercel.json` con CSP, HSTS y headers |
| Errores HTTP | Detalles crudos | Redacción de tokens + 500 genérico sin stack traces |

## 2. Cambios de código

- `backend_fastapi/app/core/logging_security.py`: `RedactionFilter` y `redact()` para
  access/refresh tokens, `Bearer`, claves `sk-ant`, `AKIA`, `ghp_`, `AIza`.
- `backend_fastapi/app/core/security_middleware.py`: request ID, rate limit global,
  límite de body JSON, cabeceras de seguridad y logging de 401/403/429/5xx.
- `backend_fastapi/app/main.py`: CORS endurecido, TrustedHost, handlers de excepción
  con redacción y error 500 genérico.
- `backend_fastapi/app/routers/videos.py`: validación de magic bytes antes de escribir.
- `backend_fastapi/app/routers/clips.py`: descarga con firma o auth/ownership.
- `backend_fastapi/app/services/media_signing.py`: URLs firmadas HMAC con TTL.
- `backend_fastapi/app/routers/webhooks.py`: idempotencia de callbacks.
- `backend_fastapi/app/security/jwt.py`: migración a PyJWT.
- `backend_fastapi/app/config.py`: algoritmo JWT restringido y expiración default 480 min.
- `backend_fastapi/app/security/hashing.py`: bcrypt rounds=12 explícito.
- `backend_fastapi/app/services/publish_service.py` y `instagram_service.py`/
  `tiktok_service.py`/`youtube_service.py`: logs OAuth sin cuerpos crudos.
- `frontend_react/vercel.json`: CSP, HSTS, XCTO, XFO, Referrer-Policy, Permissions-Policy.
- `frontend_react/package.json` + lockfiles: Vite 8.4, `@vitejs/plugin-react` 6.3,
  `react-router-dom` 7.18.7; `npm audit` 0.
- `backend_fastapi/requirements.txt`: FastAPI 0.165, Starlette 1.10, PyJWT, multipart,
  requests y dotenv parcheados.

## 3. Acciones manuales obligatorias

Estas acciones no se pueden completar solo con el código:

1. **Rotar claves expuestas en el historial.** El historial contiene material de claves
   (proveedor Anthropic y AWS). Rotar/revocar esas claves y, si el repo se considera
   comprometido, limpiar el historial con `git filter-repo`/BFG y coordinar el force
   push. No se imprime ningún valor.
2. **Configurar el hosting** con:
   - `JWT_SECRET` fuerte y `JWT_ALGORITHM=HS256`.
   - `VAULT_KEY` de 32 bytes persistente.
   - `STORAGE_SIGN_KEY` fuerte (o asumir el fallback a `JWT_SECRET`).
   - `RUNPOD_WEBHOOK_SECRET` obligatorio en producción.
   - `ALLOWED_HOSTS`, `CORS_ORIGIN_REGEX` y `SECURITY_RATE_LIMIT` según el dominio.
   - `APP_ENV=production`.
3. **HTTPS/HSTS** en Vercel/Render/Cloudflare. Verificar con `curl -I` que HSTS,
   CSP, XCTO, XFO y Referrer-Policy estén presentes. La app confía en el proxy para
   HTTPS; no agregar un redirect interno que pueda generar loops.
4. **Base de datos:** el compose usa el usuario de `POSTGRES_USER` (superusuario).
   Para producción, crear un rol de aplicación con privilegios mínimos para runtime y
   reservar el owner para migraciones. RLS de PostgREST/Supabase **no aplica** a este
   backend propio: el control de acceso es app-level (ownership por `user_id`) + ORM
   parametrizado. Si se adopta RLS, hacerlo con `SET LOCAL app.user_id` y políticas
   deny-by-default en una migración revisada.
5. **JWT en localStorage:** sigue pendiente migrar a cookie `HttpOnly; Secure; SameSite`.
   Mitigaciones actuales: CSP estricta, sin sinks XSS (`dangerouslySetInnerHTML`), JWT de
   8 h y URLs de media firmadas. La migración completa requiere cambiar login/logout,
   `apiClient`, `AuthProvider`, `usePublishSSE` y el handler SSE; hacerlo en una rama
   dedicada con pruebas de navegador.
6. **SSE de publicación:** usa el JWT como query param (`?token=`) porque `EventSource`
   no permite headers. Migrar a cookie o a un token SSE de corta duración firmado.
7. **Dependencias del worker:** `pip-audit -r requirements-worker.txt` dio **0**; dejarlo en CI
   para detectar regresiones de `mediapipe`/`litellm`/`faster-whisper`.
8. **CI de seguridad:** agregar un workflow con `pytest --cov`, `pip-audit`, `npm audit`
   y `npm run build` para que estas regresiones no vuelvan.

## 3.1 Riesgos aceptados / pendientes

- `JWT` en `localStorage` y token SSE en query: riesgo residual de XSS/logs. Mitigado
  parcialmente por CSP y por no tener sinks XSS; pendiente migración a cookies.
- Rate limit en memoria: no se comparte entre réplicas. Para multi-instancia, usar
  Redis/Upstash.
- CSP del frontend: validada con build, no con navegador real. Verificar en producción
  que Google Fonts, Bootstrap Icons y las llamadas a la API no queden bloqueadas.
- Dependencias del worker GPU: auditadas (0 vulnerabilidades); mantener el chequeo en CI.

## 4. Verificación

```bash
# Backend
pytest backend_fastapi/tests -q --cov=backend_fastapi/app
pip-audit -r backend_fastapi/requirements.txt

# Frontend
cd frontend_react
npm ci
npm run build
npm audit

# Headers (producción)
curl -sI https://clipsai.xyz/ | grep -Ei 'strict-transport|content-security|x-content-type|x-frame|referrer-policy'
curl -sI https://api.clipsai.xyz/health | grep -Ei 'strict-transport|content-security|x-content-type|x-frame|referrer-policy|x-request-id'
```

Resultado esperado en el repo: tests existentes en verde (salvo los 13 fallos
preexistentes de `main`), `pip-audit` 0 en backend/root, `npm audit` 0 y build Vite OK.

## 5. Nota de alcance

La compuerta ASH no cierra con este documento: las acciones manuales (rotación de
claves, configuración del hosting, HTTPS, rol de DB y migración a cookies) quedan
registradas arriba y deben verificarse antes de declarar `Aprobado final`.
