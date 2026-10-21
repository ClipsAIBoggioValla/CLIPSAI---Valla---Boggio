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

function wrapText(text: string, maxChars = 28): string {
  const words = text.split(/\s+/).filter(Boolean)
  if (!words.length) return text
  const lines: string[] = []
  let cur: string[] = []
  let curLen = 0
  for (const w of words) {
    const add = w.length + (cur.length ? 1 : 0)
    if (curLen + add > maxChars && cur.length) {
      lines.push(cur.join(' '))
      cur = [w]
      curLen = w.length
    } else {
      cur.push(w)
      curLen += add
    }
  }
  if (cur.length) lines.push(cur.join(' '))
  return lines.join('\\N')
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
    let start = Number(seg.start) || 0
    let end = Number(seg.end) || 0
    if (end <= start) end = start + 0.8
    let dur = end - start
    if (dur < 0.15) continue
    if (dur < 0.8) end = start + 0.8
    if (dur > 6.0) end = start + 6.0
    const text = sanitizeText(seg.text)
    if (!text) continue
    lines.push(`Dialogue: 0,${formatAssTime(start)},${formatAssTime(end)},Default,,0,0,0,,${wrapText(text, 28)}`)
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

function extractAudioWav(videoPath: string, wavPath: string): void {
  if (!hasAudioTrack(videoPath)) {
    throw new Error('El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.')
  }
  const first = run(
    'ffmpeg',
    ['-y', '-i', videoPath, '-vn', '-map', '0:a:0?', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wavPath],
    180000
  )
  if (!first.ok || !fs.existsSync(wavPath) || fs.statSync(wavPath).size === 0) {
    const fb = run('ffmpeg', ['-y', '-i', videoPath, '-vn', '-ac', '1', '-ar', '16000', wavPath], 180000)
    if (!fb.ok || !fs.existsSync(wavPath) || fs.statSync(wavPath).size === 0) {
      throw new Error(`Fallo en FFmpeg al extraer audio WAV: ${first.stderr.slice(-500) || fb.stderr.slice(-500)} (0 bytes)`)
    }
  }
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
    print(json.dumps(out))
except Exception as e:
    print(json.dumps({"__error__": str(e)}))
    sys.exit(1)
`

function transcribeWav(wavPath: string): Segment[] {
  const res = run('python3', ['-c', WHISPER_SCRIPT, wavPath], 900000)
  if (!res.ok) return []
  try {
    const parsed = JSON.parse(res.stdout.trim() || '[]')
    if (!Array.isArray(parsed) || (parsed[0] && parsed[0].__error__)) return []
    return parsed
      .filter((s: any) => s && typeof s.start === 'number' && typeof s.end === 'number' && s.text)
      .map((s: any) => ({ start: Number(s.start), end: Number(s.end), text: String(s.text) }))
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

function resolveSourceVideo(clip: Row): string | null {
  const candidates: string[] = []
  if (clip.storage_path) candidates.push(String(clip.storage_path))
  if (clip.file_path) candidates.push(String(clip.file_path))
  if (clip.video_filepath) candidates.push(String(clip.video_filepath))
  for (const c of candidates) {
    try {
      const p = path.resolve(c)
      if (fs.existsSync(p) && fs.statSync(p).isFile()) return p
    } catch {
      /* ignorar */
    }
  }
  return null
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

export async function runSubtitlePipeline(clipId: string): Promise<void> {
  const client = await pool.connect()
  let wavPath: string | null = null
  let assPath: string | null = null
  try {
    const r = await client.query(
      `SELECT c.*, v.usuario_id AS owner_id, v.file_path AS video_filepath, v.transcript AS video_transcript
       FROM clips c JOIN jobs j ON c.job_id = j.id JOIN videos v ON j.video_id = v.id
       WHERE c.id = $1`,
      [clipId]
    )
    if (r.rows.length === 0) return
    const clip = r.rows[0] as Row

    await client.query(`UPDATE clips SET status='PROCESSING', updated_at=NOW() WHERE id=$1`, [clipId])
    try {
      await client.query(`UPDATE clips SET error_log=NULL WHERE id=$1`, [clipId])
    } catch {
      /* columna ausente */
    }

    const source = resolveSourceVideo(clip)
    if (!source) throw new Error(`Video fuente no encontrado para clip ${clipId}`)

    wavPath = path.join(os.tmpdir(), `subtitle_${clipId}_${Date.now()}.wav`)
    assPath = path.join(os.tmpdir(), `subtitle_${clipId}_${Date.now()}.ass`)

    extractAudioWav(source, wavPath)
    let segments = transcribeWav(wavPath)
    if (!segments.length) {
      const clipStart = Number(clip.start_time) || 0
      const clipEnd = Number(clip.end_time) || 0
      segments = segmentsFromStoredTranscript(String(clip.video_transcript || ''), Math.max(0, clipEnd - clipStart))
    }
    if (!segments.length) throw new Error('Transcripcion vacia: no se generaron segmentos')

    // Recortar al rango del clip y desplazar a 0 (idéntico a subtitle_pipeline.py).
    const clipStart = Number(clip.start_time) || 0
    const clipEnd = Number(clip.end_time) || 0
    const clipped: Segment[] = []
    for (const seg of segments) {
      const s = Number(seg.start)
      const e = Number(seg.end)
      if (e <= s) continue
      if (e < clipStart || s > clipEnd) continue
      const cs = Math.max(s, clipStart)
      const ce = Math.min(e, clipEnd)
      if (ce > cs) clipped.push({ start: cs - clipStart, end: ce - clipStart, text: String(seg.text) })
    }
    const target = clipped.length ? clipped : segments

    fs.writeFileSync(assPath, generateAssContent(target, String(clip.title || clip.id)), 'utf-8')

    const outPath = outputPathFor(source, clipId)
    const burn = run(
      'ffmpeg',
      ['-y', '-i', source, '-vf', `ass=${assPath.replace(/\\/g, '/')}`, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', outPath],
      300000
    )
    if (!burn.ok || !fs.existsSync(outPath) || fs.statSync(outPath).size === 0) {
      throw new Error(`FFmpeg burned-in falló: ${burn.stderr.slice(-600)}`)
    }

    await client.query(`UPDATE clips SET status='COMPLETED', file_path=$1, updated_at=NOW() WHERE id=$2`, [outPath, clipId])
    try {
      await client.query(`UPDATE clips SET error_log=NULL WHERE id=$1`, [clipId])
    } catch {
      /* columna ausente */
    }
  } catch (err: unknown) {
    const e = err as Error
    const errorLog = `${e?.name || 'Error'}: ${e?.message || String(err)}\n${e?.stack || ''}`
    console.error(`[subtitles] pipeline falló para clip ${clipId}:`, e?.message || err)
    await markFailed(clipId, errorLog)
  } finally {
    for (const p of [wavPath, assPath]) {
      if (p) {
        try {
          if (fs.existsSync(p)) fs.unlinkSync(p)
        } catch {
          /* ignorar */
        }
      }
    }
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

function clipResponse(row: Row): Record<string, unknown> {
  return {
    id: row.id,
    video_id: row.video_id ?? null,
    job_id: row.job_id,
    title: row.title ?? null,
    start_time: Number(row.start_time) || 0,
    end_time: Number(row.end_time) || 0,
    score: row.score !== null && row.score !== undefined ? Number(row.score) : null,
    tags: row.tags ?? null,
    storage_path: (row.file_path as string) ?? null,
    file_path: null,
    stream_url: null,
    duration: null,
    has_ass: false,
    has_hook: false,
    status: (row.status as string) || 'ready',
    published_platform: (row.published_platform as string | null) ?? null,
    social_post_id: (row.social_post_id as string | null) ?? null,
    social_post_url: (row.social_post_url as string | null) ?? null,
    published_at: row.published_at ? new Date(row.published_at as string).toISOString() : null,
    publication_status: (row.publication_status as string | null) ?? null,
    social_network: (row.social_network as string | null) ?? null,
    created_at: row.created_at ? new Date(row.created_at as string).toISOString() : new Date().toISOString(),
    updated_at: row.updated_at ? new Date(row.updated_at as string).toISOString() : new Date().toISOString(),
  }
}

subtitlesRouter.post('/:clipId/subtitles', authMiddleware, async (req: AuthRequest, res: Response) => {
  const clipId = String((req.params as Record<string, string>).clipId)
  if (!UUID_RE.test(clipId)) return res.status(422).json({ detail: 'clip_id debe ser UUID válido' })

  const client = await pool.connect()
  try {
    // Verifica existencia (404) y ownership (403), como _get_clip_or_404 + _assert_ownership.
    const exists = await client.query('SELECT id FROM clips WHERE id = $1', [clipId])
    if (exists.rows.length === 0) return res.status(404).json({ detail: 'Clip no encontrado' })

    const row = await requireOwnedClip(clipId, String(req.user!.id), client)
    if (!row) return res.status(403).json({ detail: 'No autorizado para este clip' })

    if (String(row.status) === 'PROCESSING') {
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
    const exists = await client.query('SELECT id FROM clips WHERE id = $1', [clipId])
    if (exists.rows.length === 0) return res.status(404).json({ detail: 'Clip no encontrado' })

    const row = await requireOwnedClip(clipId, String(req.user!.id), client)
    if (!row) return res.status(403).json({ detail: 'No autorizado para este clip' })

    return res.json(clipResponse(row))
  } catch (err) {
    console.error('GET /clips/:clipId/subtitles/status error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})
