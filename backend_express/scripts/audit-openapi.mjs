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
import path from 'path'
import { fileURLToPath } from 'url'
import { collectDocumentedRoutes, collectMountedRoutes } from './_audit-shared.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const { swaggerSpec } = await import(path.join(root, 'dist/docs/swagger.js'))

const documented = collectDocumentedRoutes(swaggerSpec)
const actual = collectMountedRoutes(root)

const missing = [...actual].filter(r => !documented.has(r)).sort()
const ghost = [...documented].filter(r => !actual.has(r)).sort()

console.info(`OpenAPI ${swaggerSpec.openapi} — "${swaggerSpec.info?.title}" v${swaggerSpec.info?.version}`)
console.info(`Rutas montadas en código: ${actual.size}`)
console.info(`Rutas documentadas:       ${documented.size}`)

if (missing.length) {
  console.info(`\nSIN DOCUMENTAR (${missing.length}):`)
  missing.forEach(r => console.info(`  x ${r}`))
}
if (ghost.length) {
  console.info(`\nFANTASMA — documentada pero sin ruta real (${ghost.length}):`)
  ghost.forEach(r => console.info(`  ! ${r}`))
}

if (missing.length || ghost.length) {
  console.error('\nPARIDAD FALLIDA')
  process.exit(1)
}
console.info('\nPARIDAD OK — spec y codigo coinciden al 100%')
