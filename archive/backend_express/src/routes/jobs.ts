import { Router } from 'express'
import fs from 'fs'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'
import { logger } from '../lib/logger.js'

export const jobsRouter = Router()

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

function parseTimeString(s: string): number {
  if (!s) return 0
  try {
    if (s.includes(':')) return hmsToSeconds(s)
    return parseFloat(s)
  } catch {
    return 0
  }
}

function hmsToSeconds(s: string): number {
  const parts = s.split(':')
  if (parts.length === 3) return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseFloat(parts[2])
  if (parts.length === 2) return parseInt(parts[0], 10) * 60 + parseFloat(parts[1])
  return parseFloat(s)
}

function parseTimeToSeconds(value: unknown): number {
  if (value === null || value === undefined) return 0
  if (typeof value === 'number') return value
  return parseTimeString(String(value).trim())
}

function envValue(name: string): string {
  return (process.env[name] || '').trim()
}

function getProvider(): string {
  const anthropic = envValue('ANTHROPIC_API_KEY')
  const openai = envValue('OPENAI_API_KEY')
  const openrouter = envValue('OPENROUTER_API_KEY')
  const deepseek = envValue('DEEPSEEK_API_KEY')
  return anthropic ? 'anthropic' : openai ? 'openai' : openrouter ? 'openrouter' : deepseek ? 'deepseek' : 'none'
}

// ----------------------------------------------------------------------------
// Validaciones de entrada del engine
// ----------------------------------------------------------------------------

function requireNonEmptyPath(value: string, emptyMessage: string): void {
  if (!value || !value.trim()) throw new Error(emptyMessage)
}

function requireFileOnDisk(filePath: string, notFoundMessage: string): void {
  if (!fs.existsSync(filePath)) throw new Error(notFoundMessage)
}

function assertVideoNotEmpty(videoPath: string): void {
  try {
    const st = fs.statSync(videoPath)
    if (st.size === 0) throw new Error(`Video vacío (0 bytes): ${videoPath}`)
  } catch (e) {
    if (e instanceof Error && e.message.includes('Video')) throw e
    // ignorar stat warning
  }
}

function validateEngineInputs(videoPath: string, transcriptionPath: string): void {
  // Verificación de ruta física antes de Whisper/FFmpeg (evitar ENOENT y código 4)
  requireNonEmptyPath(videoPath, 'Ruta de video vacía — verificar video.filepath en BD')
  requireFileOnDisk(videoPath, `Video no encontrado en disco: ${videoPath} (os.path.exists=False)`)
  assertVideoNotEmpty(videoPath)
  requireNonEmptyPath(transcriptionPath, `Transcripción no encontrada: transcriptionPath vacío para video ${videoPath}`)
  requireFileOnDisk(transcriptionPath, `Transcripción no encontrada en disco: ${transcriptionPath}`)
}

// ----------------------------------------------------------------------------
// Ejecución del engine real (engine.py vía child_process)
// ----------------------------------------------------------------------------

function logEngineOk(clips: Array<Record<string, unknown>>): void {
  logger.info(`[engine:express] engine real OK ${clips.length} clips`)
}

function requireEngineSuccess(parsed: any): void {
  if (parsed?.exito !== false) return
  logger.error(`[engine:express] engine exito=false tipo=${parsed.error_tipo} err=${parsed.error}`)
  throw new Error(parsed.error || 'engine falló')
}

function clipsPayloadOf(parsed: any): { clips: unknown; engine: string } | null {
  if (parsed?.clips) {
    const clips = (parsed as { clips?: unknown }).clips
    if (Array.isArray(clips) && clips.length > 0) logEngineOk(clips as Array<Record<string, unknown>>)
    return { clips, engine: 'real' }
  }
  return null
}

function parseEngineOutput(stdout: string, provider: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(stdout)
    requireEngineSuccess(parsed)
    const payload = clipsPayloadOf(parsed)
    if (payload) return { ...payload, provider }
  } catch (e) {
    logger.error('[engine:express] parse engine JSON fallo', e)
  }
  return null
}

function spawnStderrOf(res: import('child_process').SpawnSyncReturns<string>): string {
  return (res.stderr as unknown as string) || String(res.error || '') || ''
}

function spawnDetailMessage(res: import('child_process').SpawnSyncReturns<string>, stderr: string, stdout: string): string {
  if (stderr.trim()) return stderr.trim().slice(0, 800)
  if (stdout.trim()) return stdout.trim().slice(0, 800)
  return `exit code ${res.status}`
}

function engineSpawnDetail(res: import('child_process').SpawnSyncReturns<string>): string {
  const stderr = spawnStderrOf(res)
  const stdout = (res.stdout as unknown as string) || ''
  logger.error(`[engine:express] spawn fallo status=${res.status} stderr=${String(stderr).slice(0, 800)} stdout=${String(stdout).slice(0,500)}`)
  // Propagar error descriptivo en lugar de solo código "4"
  return spawnDetailMessage(res, stderr, stdout)
}

async function runPythonEngine(videoPath: string, transcriptionPath: string, provider: string): Promise<Record<string, unknown> | null> {
  const { spawnSync } = await import('child_process')
  const path = await import('path')
  const root = path.resolve(process.cwd(), '..')
  const enginePath = path.join(root, 'engine.py')
  if (!fs.existsSync(enginePath)) {
    throw new Error(`engine.py no encontrado en ${enginePath} — verificar despliegue`)
  }
  const env = { ...process.env }
  const res = spawnSync('python', [enginePath, videoPath, transcriptionPath, '--json'], { timeout: 20000, encoding: 'utf-8', env })
  if (!(res.status === 0 && res.stdout)) {
    throw new Error(`FFmpeg/engine spawn falló (code=${res.status}): ${engineSpawnDetail(res)}`)
  }
  return parseEngineOutput(res.stdout, provider)
}

function isPropagableEngineError(e: unknown): boolean {
  return e instanceof Error && (e.message.includes('spawn falló') || e.message.includes('engine.py no encontrado'))
}

function logEngineKeys(provider: string): void {
  logger.info(`[engine:express] provider=${provider} ANTHROPIC=${!!process.env.ANTHROPIC_API_KEY} OPENAI=${!!process.env.OPENAI_API_KEY} OPENROUTER=${!!process.env.OPENROUTER_API_KEY}`)
}

function logSpawnException(e: unknown): void {
  logger.error('[engine:express] spawn exception', e, e instanceof Error ? e.stack : '')
}

async function runClipEngine(videoPath: string, transcriptionPath: string): Promise<Record<string, unknown>> {
  validateEngineInputs(videoPath, transcriptionPath)
  const provider = getProvider()
  logEngineKeys(provider)
  // Try real Python engine via child_process (soporta ANTHROPIC_API_KEY/OPENAI_API_KEY/OPENROUTER_API_KEY/DEEPSEEK)
  try {
    const parsed = await runPythonEngine(videoPath, transcriptionPath, provider)
    if (parsed) return parsed
  } catch (e) {
    logSpawnException(e)
    if (isPropagableEngineError(e)) throw e
  }
  // Intento directo Anthropic/OpenRouter si python falló y hay key: todavia no esta
  // implementado; se deja constancia y se propaga el error descriptivo mas abajo.
  if (provider !== 'none') {
    logger.warn(`[engine:express] fallback LLM directo no implementado (provider=${provider})`)
  }
  // Modo 100% real — sin fallback de prueba. Error descriptivo con causa raíz
  throw new Error(`Engine real no disponible o falló — verificar ANTHROPIC_API_KEY, engine.py y que video/transcripción existan (provider=${provider}). Revisar logs spawn previos para código de salida.`)
}

function buildFallback(_videoId: string, _preview: string): Record<string, unknown> {
  // Deshabilitado en modo 100% real — no genera clips sintéticos
  throw new Error('buildFallback deshabilitado en modo 100% real')
}

/**
 * Ejecuta el pipeline completo de un job (engine de clips + persistencia).
 * Exportado para que `routes/videos.ts` pueda lanzar el job del video de
 * muestra (`POST /videos/sample`) en background, igual que FastAPI.
 */
function jobFailureStack(err: unknown): string {
  return err instanceof Error ? err.stack ?? '' : ''
}

function shortJobMessage(err: unknown): string {
  return err instanceof Error ? String(err.message).trim() : String(err).trim()
}

function jobErrorMessageTooVague(rawMsg: string): boolean {
  return !rawMsg || rawMsg === '4' || rawMsg.length <= 4
}

function errorNameOf(err: unknown): string {
  if (err instanceof Error) return err.name
  return 'Error'
}

function vagueJobMessage(jobId: string, rawMsg: string, stack: string, err: unknown): string {
  return `${errorNameOf(err)}: ${rawMsg || 'error sin mensaje'} — Fallo en pipeline Job ${jobId}. Posibles causas: segments vacío (Whisper sin audio), filepath no existe, o FFmpeg args inválidos. Stack: ${stack.slice(0,1500)}`
}

function descriptiveJobError(jobId: string, rawMsg: string, stack: string, err: unknown): string {
  if (jobErrorMessageTooVague(rawMsg)) {
    return vagueJobMessage(jobId, rawMsg, stack, err)
  }
  const prefijo = err instanceof Error ? `${err.name}: ` : ''
  return `${prefijo}${rawMsg}${stack ? `\n${stack.slice(0,1200)}` : ''}`
}

function segmentsRangeStack(stack: string, rawMsg: string): boolean {
  if (!stack.includes('segments')) return false
  return stack.includes('RangeError') || stack.includes('index') || rawMsg.includes('index')
}

function segmentsRangeErrorMessage(jobId: string, rawMsg: string, stack: string): string | null {
  if (segmentsRangeStack(stack, rawMsg)) {
    const tail = stack ? `\n${stack.slice(0,1200)}` : ''
    return `No se detectaron segmentos de audio suficientes en el video — Whisper devolvió lista vacía. Job ${jobId}: ${rawMsg}${tail}`
  }
  return null
}

function emptyClipsErrorMessage(jobId: string, rawMsg: string): string | null {
  // Validación de arrays vacíos: mensaje descriptivo si clips vacíos
  if (rawMsg.includes('0 clips') || rawMsg.includes('no devolvió clips')) {
    return `No se detectaron segmentos de audio suficientes en el video — engine devolvió 0 clips. Job ${jobId}: verificar transcripción y audio. ${rawMsg}`
  }
  return null
}

function jobFailureMessage(jobId: string, err: unknown, stack: string): string {
  // FIX: Capturar e imprimir Traceback completo en lugar de solo str(err) == "4"
  const rawMsg = shortJobMessage(err)
  let descriptive = descriptiveJobError(jobId, rawMsg, stack, err)
  descriptive = segmentsRangeErrorMessage(jobId, rawMsg, stack) ?? descriptive
  descriptive = emptyClipsErrorMessage(jobId, rawMsg) ?? descriptive
  return descriptive
}

function errTypeName(err: unknown): string {
  return err instanceof Error ? err.name : 'Unknown'
}

async function markJobFailed(jobId: string, descriptive: string, stack: string, err: unknown): Promise<void> {
  try {
    const tbMeta = JSON.stringify({ error: descriptive.slice(0,2000), error_type: errTypeName(err), traceback: stack.slice(0,3000), engine: 'real', failed: true })
    await pool.query("UPDATE jobs SET status = 'failed', error_message = $1, result_metadata = $2::jsonb, updated_at = NOW() WHERE id = $3", [descriptive.slice(0, 2000), tbMeta, jobId])
    logger.info(`[jobs:express] job ${jobId} marcado FAILED con mensaje descriptivo`)
  } catch (dbErr) {
    logger.error(`[jobs:express] error al marcar FAILED job=${jobId}`, dbErr)
  }
}

function clipsOfResult(result: Record<string, unknown>): Record<string, unknown>[] {
  if (Array.isArray(result.clips)) return result.clips as Record<string, unknown>[]
  return Array.isArray(result) ? (result as unknown as Record<string, unknown>[]) : []
}

function clipTitleOf(item: Record<string, unknown>): string {
  return (item.title as string) || (item.titulo as string) || (item.titulo_sugerido as string) || 'Clip'
}

function clipStartOf(item: Record<string, unknown>): unknown {
  return (item.start_time as unknown) ?? (item.inicio as unknown) ?? 0
}

function clipEndOf(item: Record<string, unknown>): unknown {
  return (item.end_time as unknown) ?? (item.fin as unknown) ?? 10
}

function clipScoreOf(item: Record<string, unknown>): number | null {
  return item.score !== undefined && item.score !== null ? Number(item.score) : null
}

function clipTagsOf(item: Record<string, unknown>): unknown {
  return Array.isArray(item.tags) ? item.tags : item.tags ? [String(item.tags)] : null
}

function clipStorageOf(item: Record<string, unknown>): string {
  return (item.storage_path as string) || (item.file_path as string) || ''
}

async function persistEngineClip(client: import('pg').PoolClient, videoId: string, jobId: string, item: unknown): Promise<void> {
  if (typeof item !== 'object' || item === null) return
  const rec = item as Record<string, unknown>
  const title = clipTitleOf(rec)
  let start = parseTimeToSeconds(clipStartOf(rec))
  let end = parseTimeToSeconds(clipEndOf(rec))
  if (end <= start) end = start + 30
  const tags = clipTagsOf(rec)
  await client.query(
    'INSERT INTO clips (video_id, job_id, title, start_time, end_time, score, tags, file_path, status) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)',
    [videoId, jobId, String(title).slice(0, 255), start, end, clipScoreOf(rec), tags ? JSON.stringify(tags) : null, clipStorageOf(rec), 'ready']
  )
}

async function completeJobWithClips(client: import('pg').PoolClient, jobId: string, videoId: string, result: Record<string, unknown>): Promise<void> {
  const clipsPayload = clipsOfResult(result)
  if (clipsPayload.length === 0) {
    throw new Error('El engine real no devolvió clips (0 clips) — verificar transcripción y LLM (modo 100% real, sin fallback)')
  }
  const fresh = await client.query('SELECT id FROM jobs WHERE id = $1', [jobId])
  if (fresh.rows.length === 0) return
  await client.query('UPDATE jobs SET result_metadata = $1::jsonb, status = $2, error_message = NULL, updated_at = NOW() WHERE id = $3', [
    JSON.stringify(result),
    'completed',
    jobId,
  ])
  for (const item of clipsPayload) {
    await persistEngineClip(client, videoId, jobId, item)
  }
  logger.info(`[jobs:express] job ${jobId} completado 100% real ${clipsPayload.length} clips`)
}

async function loadJobVideo(client: import('pg').PoolClient, jobId: string): Promise<{ videoId: string; videoPath: string; transcriptionPath: string } | null> {
  const jobRes = await client.query('SELECT video_id FROM jobs WHERE id = $1', [jobId])
  if (jobRes.rows.length === 0) return null
  const videoId = jobRes.rows[0].video_id as string
  const videoRes = await client.query('SELECT file_path, transcription_filepath, transcript FROM videos WHERE id = $1', [videoId])
  if (videoRes.rows.length === 0) throw new Error('Video asociado no encontrado')
  const video = videoRes.rows[0] as Record<string, unknown>
  return { videoId, videoPath: video.file_path as string, transcriptionPath: (video.transcription_filepath as string) || '' }
}

export async function runJob(jobId: string): Promise<void> {
  const client = await pool.connect()
  try {
    await client.query("UPDATE jobs SET status = 'processing', updated_at = NOW() WHERE id = $1", [jobId])
    const loaded = await loadJobVideo(client, jobId)
    if (!loaded) return
    // Modo 100% real — sin fallback, error se propaga a FAILED
    const result: Record<string, unknown> = await runClipEngine(loaded.videoPath, loaded.transcriptionPath)
    await completeJobWithClips(client, jobId, loaded.videoId, result)
  } catch (err: unknown) {
    const stack = jobFailureStack(err)
    logger.error(`[jobs:express] fallo irrecuperable job=${jobId} — modo 100% real sin fallback`, err, stack ? `\nStack: ${stack}` : '')
    const descriptive = jobFailureMessage(jobId, err, stack)
    await markJobFailed(jobId, descriptive, stack, err)
  } finally {
    client.release()
  }
}

// ----------------------------------------------------------------------------
// Endpoints REST
// ----------------------------------------------------------------------------

function unauthorizedVideoError(vRes: { rows: Record<string, unknown>[] }, userId: string): { status: number; detail: string } | null {
  if (vRes.rows.length === 0) return { status: 404, detail: 'Video no encontrado' }
  if (String(vRes.rows[0].usuario_id) !== String(userId)) return { status: 403, detail: 'No autorizado para este video' }
  return null
}

async function createJobForVideo(client: import('pg').PoolClient, videoId: string): Promise<Record<string, unknown>> {
  const jRes = await client.query("INSERT INTO jobs (video_id, status) VALUES ($1,'pending') RETURNING id, video_id, status, error_message, result_metadata, created_at, updated_at", [videoId])
  return jRes.rows[0] as Record<string, unknown>
}

function jobResponse(job: Record<string, unknown>): Record<string, unknown> {
  return {
    id: job.id,
    video_id: job.video_id,
    status: String(job.status).toUpperCase(),
    error_message: job.error_message ?? null,
    result_metadata: job.result_metadata ?? null,
    created_at: new Date(job.created_at as string).toISOString(),
    updated_at: new Date(job.updated_at as string).toISOString(),
  }
}

jobsRouter.post('/videos/:videoId/jobs', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const videoId = String(req.params.videoId)
  if (!isValidUuid(videoId)) return res.status(422).json({ detail: 'video_id debe ser UUID válido' })
  if (!isValidUuid(userId)) return res.status(401).json({ detail: 'Usuario inválido' })

  const client = await pool.connect()
  try {
    const vRes = await client.query('SELECT id, usuario_id FROM videos WHERE id = $1', [videoId])
    const denied = unauthorizedVideoError(vRes, userId)
    if (denied) return res.status(denied.status).json({ detail: denied.detail })
    const job = await createJobForVideo(client, videoId)
    const jobId = String(job.id)
    setImmediate(() => {
      runJob(jobId).catch((e) => logger.error('runJob error', e))
    })
    return res.status(202).json(jobResponse(job))
  } catch (err) {
    logger.error('POST /videos/:videoId/jobs error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

function jobDetailResponse(row: Record<string, unknown>): Record<string, unknown> {
  return {
    id: row.id,
    video_id: row.video_id,
    status: String(row.status).toUpperCase(),
    error_message: row.error_message ?? null,
    result_metadata: row.result_metadata ?? null,
    created_at: new Date(row.created_at as string).toISOString(),
    updated_at: new Date(row.updated_at as string).toISOString(),
  }
}

jobsRouter.get('/jobs/:jobId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const jobId = String(req.params.jobId)
  if (!isValidUuid(jobId)) return res.status(422).json({ detail: 'job_id debe ser UUID válido' })
  try {
    const jRes = await pool.query('SELECT j.id, j.video_id, j.status, j.error_message, j.result_metadata, j.created_at, j.updated_at, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1', [jobId])
    if (jRes.rows.length === 0) return res.status(404).json({ detail: 'Job no encontrado' })
    const row = jRes.rows[0] as Record<string, unknown>
    if (String(row.usuario_id) !== String(userId)) return res.status(404).json({ detail: 'Job no encontrado' })
    return res.json(jobDetailResponse(row))
  } catch (err) {
    logger.error('GET /jobs/:jobId error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})

// ----------------------------------------------------------------------------
// SSE /jobs/:jobId/stream
// ----------------------------------------------------------------------------

interface SseStatus {
  progress: number
  status: string
  message: string
}

const STATUS_MAP: Record<string, SseStatus> = {
  pending: { progress: 0, status: 'pending', message: 'En cola' },
  processing: { progress: 55, status: 'scoring', message: 'Procesando con IA' },
  completed: { progress: 100, status: 'completed', message: 'Completado' },
  failed: { progress: 100, status: 'failed', message: 'Falló' },
}

interface StreamState {
  lastStatus: string | null
}

function sseError(res: import('express').Response, detail: string, interval: NodeJS.Timeout): void {
  res.write(`event: error\ndata: ${JSON.stringify({ detail })}\n\n`)
  clearInterval(interval)
  res.end()
}

async function fetchStreamRow(jobId: string): Promise<Record<string, unknown> | null> {
  const r = await pool.query('SELECT j.status, j.error_message, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1', [jobId])
  if (r.rows.length === 0) return null
  return r.rows[0] as Record<string, unknown>
}

function streamAccessError(row: Record<string, unknown> | null, userId: string): string | null {
  if (!row) return 'Job no encontrado'
  if (String(row.usuario_id) !== String(userId)) return 'No autorizado'
  return null
}

function jobStatusMap(raw: string): SseStatus {
  return STATUS_MAP[raw.toLowerCase()] ?? { progress: 0, status: raw, message: raw }
}

function isTerminalJobStatus(raw: string): boolean {
  const lower = raw.toLowerCase()
  return lower === 'completed' || lower === 'failed'
}

function writeStatusPayload(res: import('express').Response, jobId: string, row: Record<string, unknown>, mapped: SseStatus): void {
  const payload: Record<string, unknown> = { progress: mapped.progress, status: mapped.status, message: mapped.message, job_id: jobId }
  if (row.error_message) payload.error = row.error_message
  res.write(`data: ${JSON.stringify(payload)}\n\n`)
}

function finishStream(res: import('express').Response, interval: NodeJS.Timeout): void {
  res.write('event: done\ndata: {}\n\n')
  clearInterval(interval)
  res.end()
}

async function streamJobTick(res: import('express').Response, userId: string, jobId: string, interval: NodeJS.Timeout, state: StreamState): Promise<void> {
  try {
    const row = await fetchStreamRow(jobId)
    const accessError = streamAccessError(row, userId)
    if (accessError) {
      sseError(res, accessError, interval)
      return
    }
    const raw = String(row!.status)
    if (raw === state.lastStatus) return
    state.lastStatus = raw
    writeStatusPayload(res, jobId, row!, jobStatusMap(raw))
    if (isTerminalJobStatus(raw)) finishStream(res, interval)
  } catch (e) {
    logger.error('SSE stream error', e)
    clearInterval(interval)
    res.end()
  }
}

jobsRouter.get('/jobs/:jobId/stream', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const jobId = String(req.params.jobId)
  if (!isValidUuid(jobId)) return res.status(422).json({ detail: 'job_id debe ser UUID válido' })

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  // @ts-ignore
  if (typeof (res as unknown as { flushHeaders?: () => void }).flushHeaders === 'function') (res as unknown as { flushHeaders: () => void }).flushHeaders()

  const state: StreamState = { lastStatus: null }
  const interval = setInterval(async () => {
    await streamJobTick(res, userId, jobId, interval, state)
  }, 1000)

  req.on('close', () => {
    clearInterval(interval)
  })
})
