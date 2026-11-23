import { Router } from 'express'
import { spawnSync } from 'child_process'
import fs from 'fs'
import path from 'path'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const clipsRouter = Router()

const SORT_MAP: Record<string, string> = {
  created_at_desc: 'c.created_at DESC',
  created_at_asc: 'c.created_at ASC',
  score_desc: 'c.score DESC NULLS LAST, c.created_at DESC',
  score_asc: 'c.score ASC NULLS LAST, c.created_at DESC',
}

type TagBag = Record<string, unknown>
type Row = Record<string, unknown>

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

// ----------------------------------------------------------------------------
// Helpers de error / coerción (compartidos por todos los endpoints)
// ----------------------------------------------------------------------------

function isHttpError(e: unknown): e is { status: number; detail: string } {
  const err = e as { status?: number }
  return Boolean(err && err.status)
}

function respondError(res: import('express').Response, e: unknown, label: string): import('express').Response {
  if (isHttpError(e)) return res.status(e.status).json({ detail: e.detail })
  console.error(label, e)
  return res.status(500).json({ detail: 'Error interno' })
}

function toNumberOrNull(v: unknown): number | null {
  return v !== null && v !== undefined ? Number(v) : null
}

function toStrOrNull(v: unknown): string | null {
  return (v as string | null) ?? null
}

function toIsoOrNull(v: unknown): string | null {
  return v ? new Date(v as string).toISOString() : null
}

function durationOrNull(start: number, end: number): number | null {
  return Number.isFinite(start) && Number.isFinite(end) ? end - start : null
}

// ----------------------------------------------------------------------------
// Tags has_ass / has_hook
// ----------------------------------------------------------------------------

function asTagBag(tags: unknown): TagBag | null {
  if (!tags || typeof tags !== 'object' || Array.isArray(tags)) return null
  return tags as TagBag
}

function hasAppliedNested(t: TagBag, key: string): boolean {
  const nested = t[key]
  return Boolean(nested && typeof nested === 'object' && (nested as TagBag).applied)
}

function hasAssTag(t: TagBag): boolean {
  if ('has_ass' in t) return Boolean(t.has_ass)
  if (hasAppliedNested(t, 'ass')) return true
  const r = t._render as string | undefined
  return r === 'ass' || r === 'hook+ass'
}

function hasHookTag(t: TagBag): boolean {
  if ('has_hook' in t) return Boolean(t.has_hook)
  if (hasAppliedNested(t, 'hook')) return true
  const r = t._render as string | undefined
  return r === 'hook' || r === 'hook+ass'
}

function _hasAss(tags: unknown): boolean {
  const t = asTagBag(tags)
  return t !== null && hasAssTag(t)
}

function _hasHook(tags: unknown): boolean {
  const t = asTagBag(tags)
  return t !== null && hasHookTag(t)
}

// ----------------------------------------------------------------------------
// GET / — listado
// ----------------------------------------------------------------------------

interface ListQuery {
  userId: string
  q: string | undefined
  min_score: number | undefined
  sort_by: string
  page: number
  limit: number
  videoIdRaw: string | undefined
  jobIdRaw: string | undefined
  statusRaw: string | undefined
}

function parseMinScore(raw: string | undefined): number | undefined {
  return raw !== undefined && raw !== '' ? Number(raw) : undefined
}

function parsePagingInt(raw: unknown, fallback: number): number {
  return parseInt(String(raw), 10) || fallback
}

function queryTrimmed(req: AuthRequest, key: string): string | undefined {
  return typeof req.query[key] === 'string' ? (req.query[key] as string).trim() : undefined
}

function queryRaw(req: AuthRequest, key: string): string | undefined {
  return typeof req.query[key] === 'string' ? (req.query[key] as string) : undefined
}

function pagingParam(req: AuthRequest, key: string, fallback: string): string {
  return req.query[key] === undefined ? fallback : String(req.query[key])
}

function sortByOf(req: AuthRequest): string {
  const raw = queryRaw(req, 'sort_by')
  if (raw === undefined) return 'created_at_desc'
  return raw
}

function parseListQuery(req: AuthRequest): ListQuery {
  const page = Math.max(1, parsePagingInt(pagingParam(req, 'page', '1'), 1))
  const limit = Math.min(100, Math.max(1, parsePagingInt(pagingParam(req, 'limit', '10'), 10)))
  return {
    userId: req.user!.id,
    q: queryTrimmed(req, 'q'),
    min_score: parseMinScore(req.query.min_score as string | undefined),
    sort_by: sortByOf(req),
    page,
    limit,
    videoIdRaw: queryRaw(req, 'video_id'),
    jobIdRaw: queryRaw(req, 'job_id'),
    statusRaw: queryRaw(req, 'status'),
  }
}

function invalidMinScore(v: number | undefined): boolean {
  if (v === undefined) return false
  return Number.isNaN(v) || v < 0 || v > 100
}

function baseListParamError(query: ListQuery): { status: number; detail: string } | null {
  if (invalidMinScore(query.min_score)) return { status: 422, detail: 'min_score must be between 0 and 100' }
  if (!SORT_MAP[query.sort_by]) return { status: 422, detail: 'sort_by must be one of created_at_desc, created_at_asc, score_desc, score_asc' }
  return null
}

function uuidParamError(value: string | undefined, label: string): string | null {
  if (value && !isValidUuid(value)) return `${label} debe ser UUID válido`
  return null
}

function listValidationError(query: ListQuery): { status: number; detail: string } | null {
  const base = baseListParamError(query)
  if (base) return base
  const videoErr = uuidParamError(query.videoIdRaw, 'video_id')
  if (videoErr) return { status: 422, detail: videoErr }
  const jobErr = uuidParamError(query.jobIdRaw, 'job_id')
  if (jobErr) return { status: 422, detail: jobErr }
  return null
}

interface QueryFilter {
  sql: (idx: number) => string
  value: unknown
}

function searchFilters(query: ListQuery): QueryFilter[] {
  const out: QueryFilter[] = []
  if (query.q) out.push({ sql: (i) => `(c.title ILIKE $${i} OR v.transcript ILIKE $${i})`, value: `%${query.q}%` })
  if (query.min_score !== undefined) out.push({ sql: (i) => `c.score >= $${i}`, value: query.min_score })
  if (query.videoIdRaw) out.push({ sql: (i) => `(c.video_id = $${i} OR j.video_id = $${i})`, value: query.videoIdRaw })
  return out
}

function identityFilters(query: ListQuery): QueryFilter[] {
  const out: QueryFilter[] = []
  if (query.jobIdRaw) out.push({ sql: (i) => `c.job_id = $${i}`, value: query.jobIdRaw })
  if (query.statusRaw) out.push({ sql: (i) => `c.status = $${i}`, value: query.statusRaw })
  return out
}

function buildClipFilters(query: ListQuery): { conditions: string[]; values: unknown[] } {
  const conditions: string[] = ['v.usuario_id = $1']
  const values: unknown[] = [query.userId]
  for (const filter of [...searchFilters(query), ...identityFilters(query)]) {
    const idx = values.length + 1
    conditions.push(filter.sql(idx))
    values.push(filter.value)
  }
  return { conditions, values }
}

async function countUserClips(client: import('pg').PoolClient, whereClause: string, values: unknown[]): Promise<number> {
  const countRes = await client.query(
    `SELECT COUNT(*)::int AS total
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE ${whereClause}`,
    values
  )
  const total: number = countRes.rows[0]?.total ?? 0
  return total
}

async function queryUserClips(
  client: import('pg').PoolClient,
  whereClause: string,
  orderBy: string,
  values: unknown[],
  limitIdx: number,
  limit: number,
  offset: number
) {
  return client.query(
    `SELECT
       c.id, c.job_id, c.title, c.score, c.start_time, c.end_time,
       LEFT(v.transcript, 500) AS transcript,
       c.status, c.published_platform, c.social_post_url, c.published_at,
       c.created_at, c.updated_at, c.file_path, c.tags
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE ${whereClause}
     ORDER BY ${orderBy}
     LIMIT $${limitIdx} OFFSET $${limitIdx + 1}`,
    [...values, limit, offset]
  )
}

function mapClipRow(r: Row): Record<string, unknown> {
  const st = Number(r.start_time); const et = Number(r.end_time)
  return {
    id: r.id,
    job_id: r.job_id,
    title: r.title,
    score: toNumberOrNull(r.score),
    start_time: st,
    end_time: et,
    transcript: toStrOrNull(r.transcript),
    status: toStrOrNull(r.status),
    published_platform: toStrOrNull(r.published_platform),
    social_post_url: toStrOrNull(r.social_post_url),
    published_at: toIsoOrNull(r.published_at),
    created_at: new Date(r.created_at as string).toISOString(),
    updated_at: toIsoOrNull(r.updated_at),
    file_path: toStrOrNull(r.file_path),
    stream_url: `/clips/${r.id}/descarga`,
    duration: durationOrNull(st, et),
    has_ass: _hasAss(r.tags),
    has_hook: _hasHook(r.tags),
    tags: r.tags ?? null,
  }
}

clipsRouter.get('/', authMiddleware, async (req: AuthRequest, res) => {
  const query = parseListQuery(req)
  const validation = listValidationError(query)
  if (validation) return res.status(validation.status).json(validation)

  const client = await pool.connect()
  try {
    const { conditions, values } = buildClipFilters(query)
    const whereClause = conditions.join(' AND ')
    const limitIdx = values.length + 1

    const total = await countUserClips(client, whereClause, values)
    const total_pages = total > 0 ? Math.ceil(total / query.limit) : 0
    const offset = (query.page - 1) * query.limit

    const dataRes = await queryUserClips(client, whereClause, SORT_MAP[query.sort_by]!, values, limitIdx, query.limit, offset)
    const items = (dataRes.rows as Row[]).map(mapClipRow)

    return res.json({ items, total, page: query.page, limit: query.limit, total_pages })
  } catch (e) {
    return respondError(res, e, 'GET /clips error')
  } finally {
    client.release()
  }
})

// ----------------------------------------------------------------------------
// GET /:clipId — detalle
// ----------------------------------------------------------------------------

async function getClipOr404(clipId: string, userId: string, client: import('pg').PoolClient) {
  if (!isValidUuid(clipId)) throw { status: 422, detail: 'clip_id debe ser UUID válido' }
  const r = await client.query(
    `SELECT c.*, j.video_id AS job_video_id, v.usuario_id, v.file_path AS video_filepath
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE c.id = $1`,
    [clipId]
  )
  if (r.rows.length === 0) throw { status: 404, detail: 'Clip no encontrado' }
  const row = r.rows[0] as Row
  if (String(row.usuario_id) !== String(userId)) throw { status: 404, detail: 'Clip no encontrado' }
  return row
}

function mapClipDetailRow(row: Row): Record<string, unknown> {
  const st = Number(row.start_time); const et = Number(row.end_time)
  return {
    id: row.id,
    video_id: row.video_id,
    job_id: row.job_id,
    title: row.title,
    start_time: st,
    end_time: et,
    score: row.score !== null ? Number(row.score) : null,
    tags: row.tags ?? null,
    storage_path: row.file_path as string,
    file_path: row.file_path as string,
    stream_url: `/clips/${row.id}/descarga`,
    duration: durationOrNull(st, et),
    has_ass: _hasAss(row.tags),
    has_hook: _hasHook(row.tags),
    status: row.status as string,
    published_platform: toStrOrNull(row.published_platform),
    social_post_id: toStrOrNull(row.social_post_id),
    social_post_url: toStrOrNull(row.social_post_url),
    published_at: toIsoOrNull(row.published_at),
    publication_status: toStrOrNull(row.publication_status),
    social_network: toStrOrNull(row.social_network),
    created_at: new Date(row.created_at as string).toISOString(),
    updated_at: new Date((row.updated_at as string) ?? (row.created_at as string)).toISOString(),
  }
}

clipsRouter.get('/:clipId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    return res.json(mapClipDetailRow(row))
  } catch (e) {
    return respondError(res, e, 'GET /clips/:id error')
  } finally {
    client.release()
  }
})

// ----------------------------------------------------------------------------
// PATCH /:clipId
// ----------------------------------------------------------------------------

function nothingToUpdate(title: unknown, tags: unknown): boolean {
  return title === undefined && tags === undefined
}

function invalidPatchTitle(title: unknown): boolean {
  return title !== undefined && title !== null && typeof title !== 'string'
}

function invalidPatchTags(tags: unknown): boolean {
  return tags !== undefined && tags !== null && !Array.isArray(tags)
}

function patchValidationError(title: unknown, tags: unknown): { status: number; detail: string } | null {
  if (nothingToUpdate(title, tags)) return { status: 400, detail: 'Nada para actualizar' }
  if (invalidPatchTitle(title)) return { status: 422, detail: 'title debe ser string' }
  if (invalidPatchTags(tags)) return { status: 422, detail: 'tags debe ser array' }
  return null
}

function buildPatchUpdate(title: unknown, tags: unknown): { updates: string[]; values: unknown[] } {
  const updates: string[] = []
  const values: unknown[] = []
  let idx = 1
  if (title !== undefined) {
    updates.push(`title = $${idx++}`)
    values.push(title ?? null)
  }
  if (tags !== undefined) {
    updates.push(`tags = $${idx++}`)
    values.push(tags ? JSON.stringify(tags) : null)
  }
  return { updates, values }
}

function mapClipPatchRow(row: Row): Record<string, unknown> {
  return {
    id: row.id,
    video_id: row.video_id,
    job_id: row.job_id,
    title: row.title,
    start_time: Number(row.start_time),
    end_time: Number(row.end_time),
    score: row.score !== null ? Number(row.score) : null,
    tags: row.tags ?? null,
    storage_path: row.file_path as string,
    status: row.status as string,
    created_at: new Date(row.created_at as string).toISOString(),
    updated_at: new Date(row.updated_at as string).toISOString(),
  }
}

clipsRouter.patch('/:clipId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const { title, tags } = req.body as Record<string, unknown>
  const validation = patchValidationError(title, tags)
  if (validation) return res.status(validation.status).json(validation)

  const client = await pool.connect()
  try {
    await getClipOr404(clipId, String(userId), client)
    const { updates, values } = buildPatchUpdate(title, tags)
    values.push(clipId)
    const q = `UPDATE clips SET ${updates.join(', ')}, updated_at = NOW() WHERE id = $${updates.length + 1} RETURNING id, video_id, job_id, title, start_time, end_time, score, tags, file_path, status, created_at, updated_at`
    const r = await client.query(q, values)
    return res.json(mapClipPatchRow(r.rows[0] as Row))
  } catch (e) {
    return respondError(res, e, 'PATCH /clips/:id error')
  } finally {
    client.release()
  }
})

// ----------------------------------------------------------------------------
// DELETE /:clipId
// ----------------------------------------------------------------------------

function removeClipFile(filePath: string | null): void {
  if (!filePath) return
  try {
    const p = path.resolve(filePath)
    if (fs.existsSync(p)) fs.unlinkSync(p)
  } catch {}
}

clipsRouter.delete('/:clipId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    removeClipFile(row.file_path as string | null)
    await client.query('DELETE FROM clips WHERE id = $1', [clipId])
    return res.status(204).send()
  } catch (e) {
    return respondError(res, e, 'DELETE /clips/:id error')
  } finally {
    client.release()
  }
})

// ----------------------------------------------------------------------------
// GET /:clipId/descarga
// ----------------------------------------------------------------------------

function sourceCandidates(row: Row): string[] {
  const candidates: string[] = []
  if (row.file_path) candidates.push(String(row.file_path))
  if (row.video_filepath) candidates.push(String(row.video_filepath))
  return candidates
}

function isDownloadableFile(absPath: string): boolean {
  return fs.existsSync(absPath) && fs.statSync(absPath).isFile() && fs.statSync(absPath).size > 0
}

function downloadableClipPath(candidates: string[]): string | null {
  for (const p of candidates) {
    const abs = path.resolve(p)
    if (isDownloadableFile(abs)) return abs
  }
  return null
}

function clipMediaFor(ext: string): string {
  return ['.mp4', '.mov', '.avi', '.mkv'].includes(ext) ? 'video/mp4' : 'application/octet-stream'
}

clipsRouter.get('/:clipId/descarga', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    const candidates = sourceCandidates(row)
    const abs = downloadableClipPath(candidates)
    if (abs) {
      const filename = path.basename(abs) || `${clipId}.mp4`
      const media = clipMediaFor(path.extname(abs).toLowerCase())
      return res.download(abs, filename, { headers: { 'Content-Type': media } })
    }
    // Modo 100% real — sin .txt dummy de prueba
    console.error(`[CLIP DESCARGA:express] clip ${clipId} archivo no encontrado candidates=${candidates.join(',')}`)
    return res.status(404).json({ detail: `Archivo de clip no encontrado: ${candidates[0] || 'sin ruta'}. Debe existir .mp4 físico en storage.` })
  } catch (e) {
    return respondError(res, e, 'GET /clips/:id/descarga error')
  } finally {
    client.release()
  }
})

// ----------------------------------------------------------------------------
// POST /:clipId/re-render — pipeline ffmpeg en background
// ----------------------------------------------------------------------------

interface HookWindow {
  start: number
  end: number
}

interface ReRenderContext {
  clipId: string
  videoPath: string
  clipStart: number
  clipEnd: number
  enableAss: boolean
  enableHook: boolean
  hook: HookWindow | null
  assPath: string | null
  outDir: string
  outPath: string
}

interface PreparedReRenderContext extends ReRenderContext {
  srcForBurn: string
  tmpHook: string | null
}

function clampHookWindow(clipStart: number, clipEnd: number): HookWindow {
  const hookDur = 5
  let hs = (clipStart + clipEnd) / 2 - hookDur / 2
  let he = hs + hookDur
  if (hs < clipStart) { hs = clipStart; he = hs + hookDur }
  if (he > clipEnd) { he = clipEnd; hs = he - hookDur }
  return { start: Math.round(hs * 100) / 100, end: Math.round(he * 100) / 100 }
}

function computeHookWindow(clipStart: number, clipEnd: number): HookWindow | null {
  const dur = clipEnd - clipStart
  if (dur < 15 || dur > 90) return null
  return clampHookWindow(clipStart, clipEnd)
}

function generateAssFile(clipId: string, title: unknown): string | null {
  try {
    const tmpAss = path.join(process.cwd(), 'storage', `tmp_${clipId}.ass`)
    fs.mkdirSync(path.dirname(tmpAss), { recursive: true })
    // Generar ASS básico con segmentos sintéticos
    const content = `[Script Info]\nTitle: ${title ?? 'clipsai'}\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,TEST ASS\\N${String(title ?? '').slice(0, 30).toUpperCase()}\n`
    fs.writeFileSync(tmpAss, content, 'utf-8')
    return tmpAss
  } catch {
    return null
  }
}

function ffmpegCut(videoPath: string, startSec: number, durationSec: number, outPath: string): boolean {
  const res = spawnSync('ffmpeg', ['-y', '-ss', String(startSec), '-i', videoPath, '-t', String(durationSec), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-movflags', '+faststart', outPath], { timeout: 60000 })
  return res.status === 0
}

function ffmpegConcat(concatList: string, outPath: string): boolean {
  const res = spawnSync('ffmpeg', ['-y', '-f', 'concat', '-safe', '0', '-i', concatList, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-movflags', '+faststart', outPath], { timeout: 60000 })
  return res.status === 0
}

function ffmpegBurnAss(burnSrc: string, assPath: string, outPath: string): void {
  const vf = `ass=${assPath.replace(/\\/g, '/').replace(/:/g, '\\:')}`
  const res = spawnSync('ffmpeg', ['-y', '-i', burnSrc, '-vf', vf, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-movflags', '+faststart', outPath], { timeout: 80000 })
  if (res.status !== 0) throw new Error(`burn falló: ${res.stderr?.toString().slice(0, 400)}`)
}

function concatHookInto(videoPath: string, hook: HookWindow, clipStart: number, clipEnd: number, tmpDir: string, outPath: string): boolean {
  const hookTmp = path.join(tmpDir, 'hook.mp4')
  const clipTmp = path.join(tmpDir, 'clip.mp4')
  const concatList = path.join(tmpDir, 'list.txt')
  let ok = ffmpegCut(videoPath, hook.start, hook.end - hook.start, hookTmp)
  if (!ffmpegCut(videoPath, clipStart, clipEnd - clipStart, clipTmp)) ok = false
  if (!ok) return false
  fs.writeFileSync(concatList, `file '${hookTmp.replace(/'/g, "'\\''")}'\nfile '${clipTmp.replace(/'/g, "'\\''")}'\n`, 'utf-8')
  return ffmpegConcat(concatList, outPath)
}

function renameConcatToTmp(outPath: string): { srcForBurn: string; tmpHook: string } {
  const tmpHook = outPath + '.hook.mp4'
  fs.renameSync(outPath, tmpHook)
  return { srcForBurn: tmpHook, tmpHook }
}

function discardPartialOutput(outPath: string): void {
  if (fs.existsSync(outPath)) {
    try { fs.unlinkSync(outPath) } catch {}
  }
}

function buildHookConcat(clipId: string, videoPath: string, hook: HookWindow, clipStart: number, clipEnd: number, outPath: string): { srcForBurn: string; tmpHook: string | null } {
  const tmpDir = fs.mkdtempSync(path.join(process.cwd(), 'storage', `hook_${clipId}_`))
  try {
    if (concatHookInto(videoPath, hook, clipStart, clipEnd, tmpDir, outPath)) {
      return renameConcatToTmp(outPath)
    }
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch {}
  }
  discardPartialOutput(outPath)
  return { srcForBurn: videoPath, tmpHook: null }
}

function prepareHookSource(ctx: ReRenderContext): { srcForBurn: string; tmpHook: string | null } {
  if (ctx.enableHook && ctx.hook !== null) {
    return buildHookConcat(ctx.clipId, ctx.videoPath, ctx.hook, ctx.clipStart, ctx.clipEnd, ctx.outPath)
  }
  return { srcForBurn: ctx.videoPath, tmpHook: null }
}

function shouldReuseHookSource(ctx: PreparedReRenderContext): boolean {
  const hookStart = ctx.hook !== null ? ctx.hook.start : null
  return ctx.enableHook && hookStart !== null && ctx.srcForBurn !== ctx.videoPath
}

function resolveBurnSource(ctx: PreparedReRenderContext): { burnSrc: string; tmpCut: string | null } {
  if (shouldReuseHookSource(ctx)) return { burnSrc: ctx.srcForBurn, tmpCut: null }
  const tmpCut = path.join(ctx.outDir, `tmp_cut_${Date.now()}.mp4`)
  if (!ffmpegCut(ctx.videoPath, ctx.clipStart, ctx.clipEnd - ctx.clipStart, tmpCut)) {
    throw new Error('cut falló')
  }
  return { burnSrc: tmpCut, tmpCut }
}

function removeIfExists(p: string | null): void {
  if (p && fs.existsSync(p)) {
    try { fs.unlinkSync(p) } catch {}
  }
}

function renderWithAss(ctx: PreparedReRenderContext): void {
  const { burnSrc, tmpCut } = resolveBurnSource(ctx)
  ffmpegBurnAss(burnSrc, ctx.assPath as string, ctx.outPath)
  // Limpiar tmp
  removeIfExists(tmpCut)
  removeIfExists(ctx.tmpHook)
  removeIfExists(ctx.assPath)
}

function cutOrFail(ctx: PreparedReRenderContext): void {
  if (!ffmpegCut(ctx.videoPath, ctx.clipStart, ctx.clipEnd - ctx.clipStart, ctx.outPath)) throw new Error('cut falló')
}

function renderHookOnly(ctx: PreparedReRenderContext): void {
  if (fs.existsSync(ctx.outPath)) return
  if (!ffmpegCut(ctx.videoPath, ctx.clipStart, ctx.clipEnd - ctx.clipStart, ctx.outPath)) throw new Error('re-render hook sin ASS falló')
}

type Renderer = () => void

function assRendererOrNull(ctx: PreparedReRenderContext): Renderer | null {
  return ctx.enableAss && ctx.assPath !== null ? () => renderWithAss(ctx) : null
}

function nonAssRendererOrNull(ctx: PreparedReRenderContext): Renderer | null {
  if (ctx.enableAss) return null
  if (!ctx.enableHook) return () => cutOrFail(ctx)
  return () => renderHookOnly(ctx)
}

function performRender(ctx: PreparedReRenderContext): void {
  const assRenderer = assRendererOrNull(ctx)
  if (assRenderer) {
    assRenderer()
    return
  }
  const plainRenderer = nonAssRendererOrNull(ctx)
  if (plainRenderer) plainRenderer()
}

function executeReRenderSteps(ctx: ReRenderContext): void {
  const { srcForBurn, tmpHook } = prepareHookSource(ctx)
  performRender({ ...ctx, srcForBurn, tmpHook })
  if (!fs.existsSync(ctx.outPath) || fs.statSync(ctx.outPath).size === 0) throw new Error('re-render no produjo archivo')
}

function renderModeOf(enableAss: boolean, enableHook: boolean): string {
  return enableAss && enableHook ? 'hook+ass' : enableAss ? 'ass' : enableHook ? 'hook' : 'cut'
}

function applyHookTag(tagsPatch: Record<string, unknown>, enableHook: boolean, hook: HookWindow | null): void {
  if (enableHook && hook !== null) tagsPatch.hook = { start: hook.start, end: hook.end, applied: true, source: 're-render' }
  else if (!enableHook) tagsPatch.hook = null as unknown as object
}

function applyAssTag(tagsPatch: Record<string, unknown>, enableAss: boolean): void {
  if (enableAss) tagsPatch.ass = { applied: true }
  else if (!enableAss) tagsPatch.ass = null as unknown as object
}

function disabledTagCleanupSql(enableAss: boolean, enableHook: boolean): string[] {
  const cleanup: string[] = []
  if (!enableHook) cleanup.push("tags = tags - 'hook'")
  if (!enableAss) cleanup.push("tags = tags - 'ass'")
  return cleanup
}

async function setHasFlagsIgnoringError(clipId: string, enableAss: boolean, enableHook: boolean): Promise<void> {
  try {
    await pool.query(`UPDATE clips SET has_ass=$1, has_hook=$2 WHERE id=$3`, [enableAss, enableHook, clipId])
  } catch {}
}

async function cleanupDisabledTags(clipId: string, enableAss: boolean, enableHook: boolean): Promise<void> {
  if (enableHook && enableAss) return
  const cleanup = disabledTagCleanupSql(enableAss, enableHook)
  if (!cleanup.length) return
  await pool.query(`UPDATE clips SET ${cleanup.join(', ')} , has_ass = $1, has_hook = $2 WHERE id=$3`, [enableAss, enableHook, clipId]).catch(() => {})
  // Fallback: si columnas has_ass/has_hook no existen, ignorar error y solo limpiar tags JSON
  await setHasFlagsIgnoringError(clipId, enableAss, enableHook)
}

async function persistReRenderResult(clipId: string, outPath: string, enableAss: boolean, enableHook: boolean, hook: HookWindow | null): Promise<void> {
  // Actualizar BD — FIX explícito has_ass/has_hook
  const tagsPatch: Record<string, unknown> = {}
  // FIX auditoría: has_ass/has_hook deben reflejar enable_* explícitamente
  tagsPatch.has_ass = enableAss
  tagsPatch.has_hook = enableHook
  applyHookTag(tagsPatch, enableHook, hook)
  applyAssTag(tagsPatch, enableAss)
  tagsPatch._render = renderModeOf(enableAss, enableHook)
  tagsPatch._re_render = { enable_ass: enableAss, enable_hook: enableHook, at: new Date().toISOString(), out_path: outPath }
  // Merge + limpieza de nulls para desactivados
  // Postgres jsonb || no elimina nulls, así que hacemos update con COALESCE y luego limpieza en JS si es null
  await pool.query(`UPDATE clips SET file_path=$1, tags = COALESCE(tags,'{}'::jsonb) || $2::jsonb, status='ready', updated_at=NOW() WHERE id=$3`, [outPath, JSON.stringify(tagsPatch), clipId])
  // Si se desactivó, eliminar claves null
  await cleanupDisabledTags(clipId, enableAss, enableHook)
}

function renderErrorMessage(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e)
  return msg.slice(0, 500)
}

async function markReRenderFailure(clipId: string, message: string): Promise<void> {
  await pool.query(`UPDATE clips SET status='FAILED', tags = COALESCE(tags,'{}'::jsonb) || $1::jsonb, updated_at=NOW() WHERE id=$2`, [JSON.stringify({ _render_error: message }), clipId])
}

async function loadReRenderClip(client: import('pg').PoolClient, clipId: string): Promise<Row | null> {
  const r = await client.query(
    `SELECT c.id, c.job_id, c.title, c.start_time, c.end_time, c.file_path, c.tags, c.status,
            v.file_path AS video_filepath, v.transcript, v.transcription_filepath
     FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1`, [clipId]
  )
  if (r.rows.length === 0) return null
  return r.rows[0] as Row
}

function missingSourceVideo(videoPath: string): boolean {
  return !videoPath || !fs.existsSync(path.resolve(videoPath))
}

async function runReRenderPipeline(row: Row, clipId: string, videoPath: string, enableAss: boolean, enableHook: boolean): Promise<void> {
  const clipStart = Number(row.start_time); const clipEnd = Number(row.end_time)
  // Determinar hook si enableHook
  const hook = enableHook ? computeHookWindow(clipStart, clipEnd) : null
  // Preparar ASS si enableAss (simplificado: genera .ass mínimo si no hay transcripción)
  const assPath = enableAss ? generateAssFile(clipId, row.title) : null
  // Render con ffmpeg
  const outDir = path.join(process.cwd(), 'storage', 'clips', clipId)
  // Express storage is project storage/clips, but in docker /app/storage/clips — handle both
  const outPath = path.join(outDir, `${clipId}_rerender_${Date.now()}.mp4`)
  fs.mkdirSync(outDir, { recursive: true })
  const ctx: ReRenderContext = { clipId, videoPath, clipStart, clipEnd, enableAss, enableHook, hook, assPath, outDir, outPath }
  try {
    executeReRenderSteps(ctx)
    await persistReRenderResult(clipId, outPath, enableAss, enableHook, hook)
  } catch (e) {
    await markReRenderFailure(clipId, renderErrorMessage(e))
  }
}

async function runReRender(clipId: string, enableAss: boolean, enableHook: boolean) {
  const client = await pool.connect()
  try {
    const row = await loadReRenderClip(client, clipId)
    if (!row) return
    const videoPath = String(row.video_filepath ?? '')
    if (missingSourceVideo(videoPath)) {
      await markReRenderFailure(clipId, 'Video origen no encontrado')
      return
    }
    await runReRenderPipeline(row, clipId, videoPath, enableAss, enableHook)
  } finally {
    client.release()
  }
}

function enableFlag(body: Record<string, unknown>, key: string): boolean {
  if (body[key] === undefined) return true
  return Boolean(body[key])
}

async function reRenderClipNotFound(client: import('pg').PoolClient, clipId: string, userId: string): Promise<boolean> {
  const r = await client.query(`SELECT c.id FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1 AND v.usuario_id=$2`, [clipId, String(userId)])
  return r.rows.length === 0
}

async function reRenderBusy(client: import('pg').PoolClient, clipId: string): Promise<boolean> {
  const cur = await client.query(`SELECT status FROM clips WHERE id=$1`, [clipId])
  return cur.rows.length > 0 && String(cur.rows[0].status) === 'PROCESSING'
}

clipsRouter.post('/:clipId/re-render', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const body = req.body as Record<string, unknown>
  const ea = enableFlag(body, 'enable_ass')
  const eh = enableFlag(body, 'enable_hook')
  const client = await pool.connect()
  try {
    if (await reRenderClipNotFound(client, clipId, userId)) return res.status(404).json({ detail: 'Clip no encontrado' })
    if (await reRenderBusy(client, clipId)) return res.status(409).json({ detail: 'Clip ya en procesamiento' })
    await client.query(`UPDATE clips SET status='PROCESSING', updated_at=NOW() WHERE id=$1`, [clipId])
    setImmediate(() => { runReRender(clipId, ea, eh).catch(e => console.error('re-render error', e)) })
    return res.status(202).json({ detail: 'Re-render encolado', clip_id: clipId, status: 'PROCESSING', enable_ass: ea, enable_hook: eh })
  } catch (e) {
    return respondError(res, e, 'POST /clips/:id/re-render error')
  } finally {
    client.release()
  }
})

// ----------------------------------------------------------------------------
// POST /:clipId/retrim
// ----------------------------------------------------------------------------

function parseRetrimTime(value: unknown): number {
  return typeof value === 'number' ? value : Number(value)
}

function invalidRetrimRange(start: number, end: number): boolean {
  return Number.isNaN(start) || Number.isNaN(end) || start < 0 || end <= start
}

function retrimValidationError(start: number, end: number): { status: number; detail: string } | null {
  if (invalidRetrimRange(start, end)) return { status: 422, detail: 'start_time y end_time inválidos, end debe ser > start' }
  const duration = end - start
  if (duration < 5) return { status: 422, detail: 'Duración mínima 5s' }
  if (duration > 90) return { status: 422, detail: 'Duración máxima 90s' }
  return null
}

function existingSourcePath(candidates: string[]): string | null {
  for (const p of candidates) {
    if (fs.existsSync(path.resolve(p))) return path.resolve(p)
  }
  return null
}

function resolveRetrimSource(row: Row): string | null {
  const candidates = sourceCandidates(row)
  const found = existingSourcePath(candidates)
  if (found) return found
  return candidates[0] ? path.resolve(candidates[0]) : null
}

function missingSourceError(src: string | null): { status: number; detail: string } | null {
  if (src && fs.existsSync(src)) return null
  return { status: 404, detail: 'Video origen no encontrado para re-trim' }
}

function retrimOutPath(clipId: string, start: number, end: number): string {
  const outDir = path.join(process.cwd(), 'storage', 'retrims')
  fs.mkdirSync(outDir, { recursive: true })
  return path.join(outDir, `${clipId}_retrim_${Math.floor(start)}_${Math.floor(end)}.mp4`)
}

function retrimFfmpegError(src: string, start: number, duration: number, outPath: string): string | null {
  const cmd = spawnSync('ffmpeg', ['-y', '-ss', String(start), '-i', src, '-t', String(duration), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', outPath], { timeout: 120000 })
  if (cmd.status !== 0) {
    const stderr = cmd.stderr ? cmd.stderr.toString().slice(0, 600) : 'FFmpeg error'
    return `FFmpeg re-trim falló: ${stderr}`
  }
  return null
}

async function persistRetrim(client: import('pg').PoolClient, clipId: string, start: number, end: number, outPath: string): Promise<Record<string, unknown>> {
  const r = await client.query('UPDATE clips SET start_time = $1, end_time = $2, file_path = $3, updated_at = NOW() WHERE id = $4 RETURNING id, start_time, end_time, file_path, status', [start, end, outPath, clipId])
  const updated = r.rows[0] as Row
  return {
    clip_id: String(updated.id),
    start_time: Number(updated.start_time),
    end_time: Number(updated.end_time),
    duration: end - start,
    status: (updated.status as string) ?? 'ready',
    file_path: updated.file_path as string,
  }
}

type RetrimOutcome = { kind: 'error'; status: number; detail: string } | { kind: 'ok'; body: Record<string, unknown> }

async function runRetrim(client: import('pg').PoolClient, row: Row, clipId: string, start: number, end: number): Promise<RetrimOutcome> {
  const src = resolveRetrimSource(row)
  const sourceErr = missingSourceError(src)
  if (sourceErr) return { kind: 'error', status: sourceErr.status, detail: sourceErr.detail }
  const outPath = retrimOutPath(clipId, start, end)
  const detail = retrimFfmpegError(src as string, start, end - start, outPath)
  if (detail) return { kind: 'error', status: 500, detail }
  if (!fs.existsSync(outPath)) return { kind: 'error', status: 500, detail: 'Re-trim no produjo archivo' }
  return { kind: 'ok', body: await persistRetrim(client, clipId, start, end, outPath) }
}

clipsRouter.post('/:clipId/retrim', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const { start_time, end_time } = req.body as Record<string, unknown>
  const start = parseRetrimTime(start_time)
  const end = parseRetrimTime(end_time)

  const validation = retrimValidationError(start, end)
  if (validation) return res.status(validation.status).json(validation)

  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    const outcome = await runRetrim(client, row, clipId, start, end)
    if (outcome.kind === 'error') return res.status(outcome.status).json({ detail: outcome.detail })
    return res.json(outcome.body)
  } catch (e) {
    return respondError(res, e, 'POST /clips/:id/retrim error')
  } finally {
    client.release()
  }
})
