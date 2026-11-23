import { Router, type Response } from 'express'
import { spawnSync } from 'child_process'
import fs from 'fs'
import os from 'os'
import path from 'path'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

/**
 * Router de subtítulos — paridad 1:1 con `backend_fastapi/app/routers/subtitles.py`
 * y `backend_fastapi/app/tasks/subtitle_pipeline.py`.
 *
 *   POST /clips/:clipId/subtitles        → 202 {clip_id,status,message} | 403 | 404 | 409
 *   GET  /clips/:clipId/subtitles/status → ClipResponse | 403 | 404
 *
 * Se monta en `/clips` (mismo prefijo que FastAPI).
 */
export const subtitlesRouter = Router()

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ASS_STYLE_VERTICAL =
  'Arial,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1'

type Row = Record<string, any>

interface Segment {
  start: number
  end: number
  text: string
}

// ----------------------------------------------------------------------------
// Helpers de coerción
// ----------------------------------------------------------------------------

function secondsOrZero(v: unknown): number {
  return Number(v) || 0
}

function toStrOrNull(v: unknown): string | null {
  return (v as string | null) ?? null
}

function toNumberOrNull(v: unknown): number | null {
  return v !== null && v !== undefined ? Number(v) : null
}

function toIsoOrNull(v: unknown): string | null {
  return v ? new Date(v as string).toISOString() : null
}

function isoOrNow(v: unknown): string {
  return v ? new Date(v as string).toISOString() : new Date().toISOString()
}

// ----------------------------------------------------------------------------
// ASS generator (port de services/ass_generator.py)
// ----------------------------------------------------------------------------

function formatAssTime(seconds: number): string {
  let s = seconds
  if (s < 0) s = 0
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${h}:${String(m).padStart(2, '0')}:${sec.toFixed(2).padStart(5, '0')}`
}

function sanitizeText(text: string): string {
  let t = (text || '').trim().toUpperCase()
  if (!t) return ''
  t = t.replace(/\\/g, '\\\\').replace(/\{/g, '\\{').replace(/\}/g, '\\}')
  t = t.replace(/\r?\n/g, ' ').replace(/\s+/g, ' ').trim()
  return t
}

function pushWrappedWord(cur: string[], word: string, maxChars: number, curLen: number, lines: string[]): number {
  const add = word.length + (cur.length ? 1 : 0)
  if (curLen + add > maxChars && cur.length) {
    lines.push(cur.join(' '))
    return word.length
  }
  cur.push(word)
  return curLen + add
}

function wrapText(text: string, maxChars = 28): string {
  const words = text.split(/\s+/).filter(Boolean)
  if (!words.length) return text
  const lines: string[] = []
  const cur: string[] = []
  let curLen = 0
  for (const word of words) curLen = pushWrappedWord(cur, word, maxChars, curLen, lines)
  if (cur.length) lines.push(cur.join(' '))
  return lines.join('\\N')
}

function clampAssEnd(start: number, end: number): number {
  const dur = end - start
  if (dur < 0.8) return start + 0.8
  if (dur > 6.0) return start + 6.0
  return end
}

function assDialogueTimes(seg: Segment): { start: number; end: number } | null {
  const start = secondsOrZero(seg.start)
  let end = secondsOrZero(seg.end)
  if (end <= start) end = start + 0.8
  if (end - start < 0.15) return null
  return { start, end: clampAssEnd(start, end) }
}

function generateAssContent(segments: Segment[], title: string): string {
  const header =
    '[Script Info]\n' +
    `Title: ${title || 'clipsai'}\n` +
    'ScriptType: v4.00+\n' +
    'WrapStyle: 0\n' +
    'ScaledBorderAndShadow: yes\n' +
    'PlayResX: 1080\n' +
    'PlayResY: 1920\n' +
    'YCbCr Matrix: TV.709\n' +
    '\n' +
    '[V4+ Styles]\n' +
    'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,' +
    'Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,' +
    'Alignment,MarginL,MarginR,MarginV,Encoding\n' +
    `Style: Default,${ASS_STYLE_VERTICAL}\n` +
    '\n' +
    '[Events]\n' +
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'

  const lines: string[] = []
  for (const seg of segments) {
    const times = assDialogueTimes(seg)
    const text = sanitizeText(seg.text)
    if (times === null || !text) continue
    lines.push(`Dialogue: 0,${formatAssTime(times.start)},${formatAssTime(times.end)},Default,,0,0,0,,${wrapText(text, 28)}`)
  }
  return header + lines.join('\n')
}

// ----------------------------------------------------------------------------
// Helpers de FFmpeg / Whisper / transcripción
// ----------------------------------------------------------------------------

function run(cmd: string, args: string[], timeoutMs: number): { ok: boolean; stdout: string; stderr: string } {
  const res = spawnSync(cmd, args, { timeout: timeoutMs, encoding: 'utf-8', maxBuffer: 64 * 1024 * 1024 })
  return {
    ok: res.status === 0,
    stdout: (res.stdout || '') as string,
    stderr: ((res.stderr || '') as string) || String(res.error?.message ?? ''),
  }
}

function hasAudioTrack(videoPath: string): boolean {
  const res = run('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_type', '-of', 'default=noprint_wrappers=1:nokey=1', videoPath], 10000)
  if (!res.ok) return true // ffprobe ausente → asumir que sí (Whisper decide)
  const types = res.stdout.split('\n').map((s) => s.trim().toLowerCase()).filter(Boolean)
  return types.includes('audio')
}

function requireAudioTrack(videoPath: string): void {
  if (!hasAudioTrack(videoPath)) {
    throw new Error('El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.')
  }
}

function isNonEmptyFile(filePath: string): boolean {
  return fs.existsSync(filePath) && fs.statSync(filePath).size > 0
}

function fileMissingOrEmpty(filePath: string): boolean {
  return !isNonEmptyFile(filePath)
}

function audioExtractError(firstStderr: string, fbStderr: string): string {
  return `Fallo en FFmpeg al extraer audio WAV: ${firstStderr.slice(-500) || fbStderr.slice(-500)} (0 bytes)`
}

function wavAttemptFailed(res: { ok: boolean }, wavPath: string): boolean {
  return !res.ok || fileMissingOrEmpty(wavPath)
}

function extractAudioWav(videoPath: string, wavPath: string): void {
  requireAudioTrack(videoPath)
  const first = run(
    'ffmpeg',
    ['-y', '-i', videoPath, '-vn', '-map', '0:a:0?', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wavPath],
    180000
  )
  if (!wavAttemptFailed(first, wavPath)) return
  const fb = run('ffmpeg', ['-y', '-i', videoPath, '-vn', '-ac', '1', '-ar', '16000', wavPath], 180000)
  if (!wavAttemptFailed(fb, wavPath)) return
  throw new Error(audioExtractError(first.stderr, fb.stderr))
}

const WHISPER_SCRIPT = `
import sys, json
try:
    from faster_whisper import WhisperModel
    model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8", local_files_only=True)
    segs, _ = model.transcribe(sys.argv[1], language="es", word_timestamps=False, vad_filter=True, beam_size=5, temperature=0.0)
    out = []
    for s in segs:
        t = str(s.text).strip()
        if t:
            out.append({"start": float(s.start), "end": float(s.end), "text": t})
    sys.stdout.write(json.dumps(out))
except Exception as e:
    sys.stdout.write(json.dumps({"__error__": str(e)}))
    sys.exit(1)
`

function whisperErrorOrEmpty(parsed: unknown): boolean {
  if (!Array.isArray(parsed)) return true
  const first = parsed[0] as { __error__?: unknown } | undefined
  return Boolean(first && first.__error__)
}

function parseWhisperSegments(stdout: string): Segment[] {
  const parsed = JSON.parse(stdout.trim() || '[]')
  if (whisperErrorOrEmpty(parsed)) return []
  return (parsed as any[])
    .filter((s: any) => s && typeof s.start === 'number' && typeof s.end === 'number' && s.text)
    .map((s: any) => ({ start: Number(s.start), end: Number(s.end), text: String(s.text) }))
}

function transcribeWav(wavPath: string): Segment[] {
  const res = run('python3', ['-c', WHISPER_SCRIPT, wavPath], 900000)
  if (!res.ok) return []
  try {
    return parseWhisperSegments(res.stdout)
  } catch {
    return []
  }
}

/** Fallback cuando faster-whisper no está disponible: distribuye el transcript guardado. */
function segmentsFromStoredTranscript(transcript: string, duration: number): Segment[] {
  const text = (transcript || '').trim()
  if (!text || !(duration > 0)) return []
  const parts = text
    .split(/[.!?]+/)
    .map((t) => t.trim())
    .filter(Boolean)
  if (!parts.length) return []
  const per = duration / parts.length
  return parts.map((t, i) => ({ start: i * per, end: (i + 1) * per, text: t }))
}

function storedTranscriptSegments(clip: Row): Segment[] {
  const clipStart = secondsOrZero(clip.start_time)
  const clipEnd = secondsOrZero(clip.end_time)
  return segmentsFromStoredTranscript(String(clip.video_transcript || ''), Math.max(0, clipEnd - clipStart))
}

function transcribedOrStoredSegments(wavPath: string, clip: Row): Segment[] {
  const segments = transcribeWav(wavPath)
  return segments.length ? segments : storedTranscriptSegments(clip)
}

function sourceCandidatesForClip(clip: Row): string[] {
  const candidates: string[] = []
  if (clip.storage_path) candidates.push(String(clip.storage_path))
  if (clip.file_path) candidates.push(String(clip.file_path))
  if (clip.video_filepath) candidates.push(String(clip.video_filepath))
  return candidates
}

function isReadableFile(p: string): boolean {
  try {
    return fs.existsSync(p) && fs.statSync(p).isFile()
  } catch {
    /* ignorar */
    return false
  }
}

function existingFilePath(candidates: string[]): string | null {
  for (const c of candidates) {
    const p = path.resolve(c)
    if (isReadableFile(p)) return p
  }
  return null
}

function resolveSourceVideo(clip: Row): string | null {
  return existingFilePath(sourceCandidatesForClip(clip))
}

function outputPathFor(source: string, clipId: string): string {
  const ext = path.extname(source) || '.mp4'
  const dir = path.dirname(source)
  let out = path.join(dir, `${clipId}_subtitled${ext}`)
  if (path.resolve(out) === path.resolve(source)) out = path.join(dir, `${clipId}_subtitled_burned${ext}`)
  return out
}

async function markFailed(clipId: string, errorLog: string): Promise<void> {
  const msg = errorLog.slice(0, 8000)
  try {
    await pool.query(`UPDATE clips SET status='FAILED', tags = COALESCE(tags,'{}'::jsonb) || $1::jsonb, updated_at=NOW() WHERE id=$2`, [
      JSON.stringify({ error_log: msg.slice(0, 4000), _subtitle_error: msg.slice(0, 2000) }),
      clipId,
    ])
  } catch (err) {
    console.error('[subtitles] no se pudo marcar FAILED:', err)
  }
  // `error_log` existe en la BD migrada por FastAPI; best-effort por si Express corre aislado.
  try {
    await pool.query(`UPDATE clips SET error_log=$1 WHERE id=$2`, [msg, clipId])
  } catch {
    /* columna ausente: ignorar */
  }
}

// ----------------------------------------------------------------------------
// Pipeline
// ----------------------------------------------------------------------------

async function clearErrorLog(client: import('pg').PoolClient, clipId: string): Promise<void> {
  try {
    await client.query(`UPDATE clips SET error_log=NULL WHERE id=$1`, [clipId])
  } catch {
    /* columna ausente */
  }
}

async function loadSubtitleClip(client: import('pg').PoolClient, clipId: string): Promise<Row | null> {
  const r = await client.query(
    `SELECT c.*, v.usuario_id AS owner_id, v.file_path AS video_filepath, v.transcript AS video_transcript
     FROM clips c JOIN jobs j ON c.job_id = j.id JOIN videos v ON j.video_id = v.id
     WHERE c.id = $1`,
    [clipId]
  )
  if (r.rows.length === 0) return null
  return r.rows[0] as Row
}

function outsideClipRange(s: number, e: number, clipStart: number, clipEnd: number): boolean {
  return e < clipStart || s > clipEnd
}

function clippedSegment(seg: Segment, clipStart: number, clipEnd: number): Segment | null {
  const s = Number(seg.start)
  const e = Number(seg.end)
  if (e <= s) return null
  if (outsideClipRange(s, e, clipStart, clipEnd)) return null
  const cs = Math.max(s, clipStart)
  const ce = Math.min(e, clipEnd)
  if (ce > cs) return { start: cs - clipStart, end: ce - clipStart, text: String(seg.text) }
  return null
}

function clipSegments(segments: Segment[], clip: Row): Segment[] {
  // Recortar al rango del clip y desplazar a 0 (idéntico a subtitle_pipeline.py).
  const clipStart = secondsOrZero(clip.start_time)
  const clipEnd = secondsOrZero(clip.end_time)
  const clipped: Segment[] = []
  for (const seg of segments) {
    const piece = clippedSegment(seg, clipStart, clipEnd)
    if (piece) clipped.push(piece)
  }
  return clipped
}

function subtitleBurnArgs(source: string, assPath: string, outPath: string): string[] {
  return ['-y', '-i', source, '-vf', `ass=${assPath.replace(/\\/g, '/')}`, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', outPath]
}

function burnOk(burn: { ok: boolean }, outPath: string): boolean {
  return burn.ok && isNonEmptyFile(outPath)
}

function burnSubtitles(source: string, assPath: string, outPath: string): void {
  const burn = run('ffmpeg', subtitleBurnArgs(source, assPath, outPath), 300000)
  if (!burnOk(burn, outPath)) {
    throw new Error(`FFmpeg burned-in falló: ${burn.stderr.slice(-600)}`)
  }
}

async function executeSubtitlePipeline(client: import('pg').PoolClient, clipId: string, clip: Row, source: string, wavPath: string, assPath: string): Promise<void> {
  extractAudioWav(source, wavPath)
  const segments = transcribedOrStoredSegments(wavPath, clip)
  if (!segments.length) throw new Error('Transcripcion vacia: no se generaron segmentos')
  const clipped = clipSegments(segments, clip)
  const target = clipped.length ? clipped : segments
  fs.writeFileSync(assPath, generateAssContent(target, String(clip.title || clip.id)), 'utf-8')
  const outPath = outputPathFor(source, clipId)
  burnSubtitles(source, assPath, outPath)
  await client.query(`UPDATE clips SET status='COMPLETED', file_path=$1, updated_at=NOW() WHERE id=$2`, [outPath, clipId])
  await clearErrorLog(client, clipId)
}

function subtitleErrorLog(err: unknown): string {
  const e = err as Error
  return `${e?.name || 'Error'}: ${e?.message || String(err)}\n${e?.stack || ''}`
}

function subtitleErrorMessage(err: unknown): unknown {
  return (err as Error)?.message || err
}

async function failSubtitlePipeline(clipId: string, err: unknown): Promise<void> {
  console.error(`[subtitles] pipeline falló para clip ${clipId}:`, subtitleErrorMessage(err))
  await markFailed(clipId, subtitleErrorLog(err))
}

function removeTempFile(p: string | null): void {
  if (!p) return
  try {
    if (fs.existsSync(p)) fs.unlinkSync(p)
  } catch {
    /* ignorar */
  }
}

export async function runSubtitlePipeline(clipId: string): Promise<void> {
  const client = await pool.connect()
  let wavPath: string | null = null
  let assPath: string | null = null
  try {
    const clip = await loadSubtitleClip(client, clipId)
    if (!clip) return
    await client.query(`UPDATE clips SET status='PROCESSING', updated_at=NOW() WHERE id=$1`, [clipId])
    await clearErrorLog(client, clipId)
    const source = resolveSourceVideo(clip)
    if (!source) throw new Error(`Video fuente no encontrado para clip ${clipId}`)
    wavPath = path.join(os.tmpdir(), `subtitle_${clipId}_${Date.now()}.wav`)
    assPath = path.join(os.tmpdir(), `subtitle_${clipId}_${Date.now()}.ass`)
    await executeSubtitlePipeline(client, clipId, clip, source, wavPath, assPath)
  } catch (err: unknown) {
    await failSubtitlePipeline(clipId, err)
  } finally {
    removeTempFile(wavPath)
    removeTempFile(assPath)
    client.release()
  }
}

// ----------------------------------------------------------------------------
// Endpoints
// ----------------------------------------------------------------------------

async function getClipRow(clipId: string, userId: string, client: import('pg').PoolClient): Promise<Row> {
  const r = await client.query(
    `SELECT c.*, v.usuario_id AS owner_id, v.file_path AS video_filepath
     FROM clips c JOIN jobs j ON c.job_id = j.id JOIN videos v ON j.video_id = v.id
     WHERE c.id = $1`,
    [clipId]
  )
  return r.rows[0] as Row
}

async function requireOwnedClip(clipId: string, userId: string, client: import('pg').PoolClient): Promise<Row | null> {
  const row = await getClipRow(clipId, userId, client)
  if (!row) return null
  if (String(row.owner_id) !== String(userId)) return null
  return row
}

type ClipAccess = { kind: 'ok'; row: Row } | { kind: 'error'; status: number; detail: string }

async function clipAccessFor(client: import('pg').PoolClient, clipId: string, userId: string): Promise<ClipAccess> {
  // Verifica existencia (404) y ownership (403), como _get_clip_or_404 + _assert_ownership.
  const exists = await client.query('SELECT id FROM clips WHERE id = $1', [clipId])
  if (exists.rows.length === 0) return { kind: 'error', status: 404, detail: 'Clip no encontrado' }
  const row = await requireOwnedClip(clipId, userId, client)
  if (!row) return { kind: 'error', status: 403, detail: 'No autorizado para este clip' }
  return { kind: 'ok', row }
}

function isProcessing(row: Row): boolean {
  return String(row.status) === 'PROCESSING'
}

function clipResponse(row: Row): Record<string, unknown> {
  return {
    id: row.id,
    video_id: row.video_id ?? null,
    job_id: row.job_id,
    title: toStrOrNull(row.title),
    start_time: secondsOrZero(row.start_time),
    end_time: secondsOrZero(row.end_time),
    score: toNumberOrNull(row.score),
    tags: row.tags ?? null,
    storage_path: toStrOrNull(row.file_path),
    file_path: null,
    stream_url: null,
    duration: null,
    has_ass: false,
    has_hook: false,
    status: (row.status as string) || 'ready',
    published_platform: toStrOrNull(row.published_platform),
    social_post_id: toStrOrNull(row.social_post_id),
    social_post_url: toStrOrNull(row.social_post_url),
    published_at: toIsoOrNull(row.published_at),
    publication_status: toStrOrNull(row.publication_status),
    social_network: toStrOrNull(row.social_network),
    created_at: isoOrNow(row.created_at),
    updated_at: isoOrNow(row.updated_at),
  }
}

subtitlesRouter.post('/:clipId/subtitles', authMiddleware, async (req: AuthRequest, res: Response) => {
  const clipId = String((req.params as Record<string, string>).clipId)
  if (!UUID_RE.test(clipId)) return res.status(422).json({ detail: 'clip_id debe ser UUID válido' })

  const client = await pool.connect()
  try {
    const access = await clipAccessFor(client, clipId, String(req.user!.id))
    if (access.kind === 'error') return res.status(access.status).json({ detail: access.detail })

    if (isProcessing(access.row)) {
      return res.status(409).json({ detail: 'Clip ya en procesamiento' })
    }

    // Background (fire-and-forget), el estado se setea en el pipeline (igual que BackgroundTasks).
    setImmediate(() => {
      runSubtitlePipeline(clipId).catch((err) => console.error(`[subtitles] error clip ${clipId}:`, err))
    })

    return res.status(202).json({
      clip_id: clipId,
      status: 'PROCESSING',
      message: 'Subtitulado iniciado en background',
    })
  } catch (err) {
    console.error('POST /clips/:clipId/subtitles error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

subtitlesRouter.get('/:clipId/subtitles/status', authMiddleware, async (req: AuthRequest, res: Response) => {
  const clipId = String((req.params as Record<string, string>).clipId)
  if (!UUID_RE.test(clipId)) return res.status(422).json({ detail: 'clip_id debe ser UUID válido' })

  const client = await pool.connect()
  try {
    const access = await clipAccessFor(client, clipId, String(req.user!.id))
    if (access.kind === 'error') return res.status(access.status).json({ detail: access.detail })

    return res.json(clipResponse(access.row))
  } catch (err) {
    console.error('GET /clips/:clipId/subtitles/status error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})
