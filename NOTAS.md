# NOTAS.md

- Objetivo: Cerrar semana-1 (#111, #113 y 7 tests de #116) y avanzar semana-2.
- Estado actual: PR #154 (#114) listo para merge; rama dev activa; worker GPU en mfboggio/clipsai-worker:v38.
- Hecho: #115 (v36), #116 (v37), #117 (v38), #110 (archive/), #114 (PR #154: r2_service + purge + OAuth disconnect).
- Pendiente (en orden): #111 (vault AESGCM + rate limit + JWT + purge git), #113 (webhooks HMAC RunPod), fix 7 tests de #116.
- Archivos relevantes: backend_fastapi/app/, frontend_react/, docker-compose.yml.
- Decisiones y restricciones: stack unico FastAPI+React; AST CC <= 4; no tocar archive/.
- Como probar: pytest -q -x --tb=short
