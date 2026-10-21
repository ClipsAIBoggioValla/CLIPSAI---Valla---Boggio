#!/usr/bin/env node
/**
 * Auditoría de paridad spec↔código para Issue 14.
 *
 * Compara las operaciones realmente montadas en `src/app.ts` (prefix + sub-ruta
 * de cada router) contra las declaradas en `paths` del spec OpenAPI.
 *
 * Uso:
 *   npm run build && node scripts/audit-openapi.mjs
 *   exit 0 = paridad total · exit 1 = hay rutas sin documentar o fantasma
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const { swaggerSpec } = await import(path.join(root, 'dist/docs/swagger.js'))

/** Montajes de routers según `app.use(...)` en src/app.ts. */
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

const METHODS = 'get|post|put|patch|delete'

/** Rutas declaradas en el spec, como `METHOD /path`. */
const documented = new Set()
for (const [p, item] of Object.entries(swaggerSpec.paths ?? {})) {
  for (const method of Object.keys(item)) documented.add(`${method.toUpperCase()} ${p}`)
}

/** Rutas realmente montadas, como `METHOD /path`. */
const actual = new Set()
for (const { file, router, prefixes } of MOUNTS) {
  const src = fs.readFileSync(path.join(root, 'src/routes', file), 'utf8')
  const re = new RegExp(`${router}\\s*\\.\\s*(${METHODS})\\s*\\(\\s*'([^']*)'`, 'g')
  for (const [, method, sub] of src.matchAll(re)) {
    for (const prefix of prefixes) {
      const joined = `${prefix}${sub === '/' ? '' : sub}`.replace(/\/+$/, '') || '/'
      actual.add(`${method.toUpperCase()} ${joined.replace(/:([A-Za-z_]\w*)/g, '{$1}')}`)
    }
  }
}
actual.add('GET /health')

const missing = [...actual].filter(r => !documented.has(r)).sort()
const ghost = [...documented].filter(r => !actual.has(r)).sort()

console.log(`OpenAPI ${swaggerSpec.openapi} — "${swaggerSpec.info?.title}" v${swaggerSpec.info?.version}`)
console.log(`Rutas montadas en código: ${actual.size}`)
console.log(`Rutas documentadas:       ${documented.size}`)

if (missing.length) {
  console.log(`\nSIN DOCUMENTAR (${missing.length}):`)
  missing.forEach(r => console.log(`  x ${r}`))
}
if (ghost.length) {
  console.log(`\nFANTASMA — documentada pero sin ruta real (${ghost.length}):`)
  ghost.forEach(r => console.log(`  ! ${r}`))
}

if (missing.length || ghost.length) {
  console.error('\nPARIDAD FALLIDA')
  process.exit(1)
}
console.log('\nPARIDAD OK — spec y codigo coinciden al 100%')