/**
 * Helpers compartidos por los scripts de auditoría (audit-openapi.mjs, audit-parity.mjs).
 *
 * Centraliza la tabla de montajes de routers y el escaneo de rutas reales para
 * que ambos scripts no dupliquen esa lógica (Issue 42 — Duplic%).
 */
import fs from 'fs'
import path from 'path'

/** Montajes de routers según `app.use(...)` en src/app.ts. */
export const MOUNTS = [
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

export const METHODS = 'get|post|put|patch|delete'

/** Normaliza un path de Express (`:id`) o de OpenAPI (`{id}`) a una forma comparable. */
export function normalizePath(p) {
  return p
    .replace(/\/+$/, '')
    .replace(/:[A-Za-z_]\w*/g, '{}')
    .replace(/\{[^}]+\}/g, '{}')
}

/** Rutas declaradas en el spec OpenAPI, como `METHOD /path`. */
export function collectDocumentedRoutes(swaggerSpec) {
  const documented = new Set()
  for (const [p, item] of Object.entries(swaggerSpec.paths ?? {})) {
    for (const method of Object.keys(item)) documented.add(`${method.toUpperCase()} ${p}`)
  }
  return documented
}

/** Rutas realmente montadas en el código, como `METHOD /path`. */
export function collectMountedRoutes(root, { normalize = false } = {}) {
  const actual = new Set()
  for (const { file, router, prefixes } of MOUNTS) {
    const src = fs.readFileSync(path.join(root, 'src/routes', file), 'utf8')
    const re = new RegExp(`${router}\\s*\\.\\s*(${METHODS})\\s*\\(\\s*'([^']*)'`, 'g')
    for (const [, method, sub] of src.matchAll(re)) {
      for (const prefix of prefixes) {
        const joined = `${prefix}${sub === '/' ? '' : sub}`.replace(/\/+$/, '') || '/'
        const p = joined.replace(/:([A-Za-z_]\w*)/g, '{$1}')
        actual.add(`${method.toUpperCase()} ${normalize ? normalizePath(p) : p}`)
      }
    }
  }
  actual.add('GET /health')
  return actual
}
