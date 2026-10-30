#!/usr/bin/env node
/**
 * Auditoría de PARIDAD FASTAPI ↔ EXPRESS (Issue 14).
 *
 * Compara el inventario de rutas realmente montadas por FastAPI (snapshot
 * autoritativo, `fastapi-routes.json`) contra las rutas que Express monta en
 * `src/app.ts` + `src/routes/*.ts`.
 *
 * Cómo regenerar el snapshot de FastAPI. El snapshot debe reflejar la superficie
 * que FastAPI expone realmente; como la imagen ya incluye `backend/` (routers
 * opcionales `retrim`/`stream`) y el alias `backend_fastapi.*` -> `app.*`
 * (`backend_fastapi/docker-sitecustomize.py`), basta correr la imagen desplegada:
 *
 *   docker compose build backend_fastapi
 *   docker compose run --rm --no-deps -T backend_fastapi python -c "
 *   import json
 *   from app.main import app
 *   out = []
 *   seen = set()
 *   for r in app.routes:
 *       methods = sorted(m for m in getattr(r,'methods',[]) or [] if m not in ('HEAD','OPTIONS'))
 *       if not methods:
 *           continue
 *       key = (r.path, tuple(methods))
 *       if key in seen:
 *           continue
 *       seen.add(key)
 *       out.append({'path': r.path, 'methods': methods})
 *   out.sort(key=lambda x: x['path'])
 *   print(json.dumps(out, indent=1))
 *   " > backend_express/scripts/fastapi-routes.json
 *
 * Importante: NO montar `backend_fastapi/app` por encima del de la imagen, porque
 * entonces faltaría `/backend` y el inventario saldría con 60 rutas en vez de 62
 * (antes de Issue 35 la superficie de FastAPI dependía del layout de ejecución).
 *
 * Uso:
 *   npm run build && node scripts/audit-parity.mjs
 *   exit 0 = paridad 1:1 total · exit 1 = hay rutas que difieren
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { swaggerSpec } from '../dist/docs/swagger.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/** Normaliza `:id`/`{id}` a `{}` para comparar sin depender del nombre del parámetro. */
const norm = (p) => p.replace(/\/+$/, '').replace(/:[A-Za-z_]\w*/g, '{}').replace(/\{[^}]+\}/g, '{}')

/** ---- Inventario FastAPI (snapshot) ---- */
const fastapi = JSON.parse(
  fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), 'fastapi-routes.json'), 'utf8')
)
const fastSet = new Set()
for (const r of fastapi) {
  for (const m of r.methods) {
    if (m === 'HEAD' || m === 'OPTIONS') continue
    fastSet.add(`${m} ${norm(r.path)}`)
  }
}

/** ---- Inventario Express: routers + montajes directos en app.ts ---- */
const MOUNTS = [
  { file: 'auth.ts', router: 'authRouter', prefixes: ['/auth'] },
  { file: 'auth.ts', router: 'compatAuthRouter', prefixes: [''] },
  { file: 'videos.ts', router: 'videosRouter', prefixes: ['/videos'] },
  { file: 'jobs.ts', router: 'jobsRouter', prefixes: [''] },
  { file: 'export.ts', router: 'exportRouter', prefixes: [''] },
  { file: 'metrics.ts', router: 'metricsRouter', prefixes: [''] },
  { file: 'stats.ts', router: 'statsRouter', prefixes: ['/stats'] },
  { file: 'clips.ts', router: 'clipsRouter', prefixes: ['/clips'] },
  { file: 'publish.ts', router: 'publishRouter', prefixes: [''] },
  { file: 'users.ts', router: 'usersRouter', prefixes: ['', '/api'] },
  { file: 'subtitles.ts', router: 'subtitlesRouter', prefixes: ['/clips'] },
  { file: 'socialAuth.ts', router: 'socialAuthRouter', prefixes: ['/auth/social'] },
  { file: 'apiVideos.ts', router: 'apiVideosRouter', prefixes: ['/api/videos'] },
]

/** Montajes directos en `app.ts` (docs UI, health, spec). */
const APP_MOUNTS = [
  'GET /health',
  'GET /openapi.json',
  'GET /api-docs.json',
  'GET /redoc',
  'GET /docs/oauth2-redirect',
  'GET /docs',
  'GET /api-docs',
]

const METHODS = 'get|post|put|patch|delete'
const express = new Set([...APP_MOUNTS])
for (const { file, router, prefixes } of MOUNTS) {
  const src = fs.readFileSync(path.join(root, 'src/routes', file), 'utf8')
  const re = new RegExp(`${router}\\s*\\.\\s*(${METHODS})\\s*\\(\\s*'([^']*)'`, 'g')
  for (const [, method, sub] of src.matchAll(re)) {
    for (const prefix of prefixes) {
      const joined = `${prefix}${sub === '/' ? '' : sub}`.replace(/\/+$/, '') || '/'
      express.add(`${method.toUpperCase()} ${norm(joined)}`)
    }
  }
}

/** El spec OpenAPI de Express debe documentar TODAS sus rutas montadas. */
const documented = new Set()
for (const [p, item] of Object.entries(swaggerSpec.paths ?? {})) {
  for (const method of Object.keys(item)) documented.add(`${method.toUpperCase()} ${norm(p)}`)
}

/**
 * Superset deliberado: endpoints de infra/docs que Express conserva y FastAPI no
 * tiene (o que son viewers, no API). No rompen la paridad funcional.
 *   - `/api-docs`, `/api-docs.json`: criterio de aceptación de Issue 14.
 * Un spec no puede documentarse a sí mismo: `/openapi.json`, `/redoc` y los
 * viewers de Swagger quedan fuera del chequeo de "documentado".
 */
const DOCS_SUPERSET = new Set(['GET /api-docs', 'GET /api-docs.json'])
const isDocsRoute = (r) =>
  r.startsWith('GET /docs') || r.startsWith('GET /api-docs') || r.startsWith('GET /openapi.json') || r.startsWith('GET /redoc')

const onlyFastapi = [...fastSet].filter((r) => !express.has(r)).sort()
const onlyExpress = [...express].filter((r) => !fastSet.has(r) && !DOCS_SUPERSET.has(r)).sort()
const undocumented = [...express].filter((r) => !documented.has(r) && !isDocsRoute(r)).sort()


console.info(`FastAPI rutas: ${fastSet.size} | Express rutas: ${express.size} | Documentadas: ${documented.size}`)

let ok = true
if (onlyFastapi.length) {
  ok = false
  console.info(`\nSOLO EN FASTAPI (faltan en Express) — ${onlyFastapi.length}:`)
  onlyFastapi.forEach((r) => console.info(`  - ${r}`))
}
if (onlyExpress.length) {
  ok = false
  console.info(`\nSOLO EN EXPRESS (rutas extra) — ${onlyExpress.length}:`)
  onlyExpress.forEach((r) => console.info(`  + ${r}`))
}
if (undocumented.length) {
  ok = false
  console.info(`\nEXPRESS SIN DOCUMENTAR EN SWAGGER — ${undocumented.length}:`)
  undocumented.forEach((r) => console.info(`  ? ${r}`))
}

if (ok) {
  console.info('\nPARIDAD 1:1 OK — FastAPI y Express exponen exactamente las mismas rutas de API')
} else {
  console.error('\nPARIDAD FALLIDA')
  process.exit(1)
}