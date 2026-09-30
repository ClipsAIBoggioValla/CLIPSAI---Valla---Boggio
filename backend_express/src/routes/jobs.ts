import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const jobsRouter = Router()

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

function parseTimeToSeconds(value: unknown): number {
  if (value === null || value === undefined) return 0
  if (typeof value === 'number') return value
  const s = String(value).trim()
  if (!s) return 0
  try {
    if (s.includes(':')) {
      const parts = s.split(':')
      if (parts.length === 3) return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseFloat(parts[2])
      if (parts.length === 2) return parseInt(parts[0], 10) * 60 + parseFloat(parts[1])
    }
    return parseFloat(s)
  } catch {
    return 0
  }
}

function getProvider(): string {
  const anthropic = (process.env.ANTHROPIC_API_KEY || '').trim()
  const openai = (process.env.OPENAI_API_KEY || '').trim()
  const openrouter = (process.env.OPENROUTER_API_KEY || '').trim()
  const deepseek = (process.env.DEEPSEEK_API_KEY || '').trim()
  if (anthropic && anthropic.startsWith('sk-ant')) return 'anthropic'
  if (anthropic) return 'anthropic'
  if (openai) return 'openai'
  if (openrouter) return 'openrouter'
  if (deepseek) return 'deepseek'
  return 'none'
}

async function runClipEngine(videoPath: string, transcriptionPath: string): Promise<Record<string, unknown>> {
  const fs = await import('fs')
  // Verificación de ruta física antes de Whisper/FFmpeg (evitar ENOENT y código 4)
  if (!videoPath || !videoPath.trim()) {
    throw new Error('Ruta de video vacía — verificar video.filepath en BD')
  }
  if (!fs.existsSync(videoPath)) {
    throw new Error(`Video no encontrado en disco: ${videoPath} (os.path.exists=False)`)
  }
  try {
    const st = fs.statSync(videoPath)
    if (st.size === 0) throw new Error(`Video vacío (0 bytes): ${videoPath}`)
  } catch (e) {
    if (e instanceof Error && e.message.includes('Video')) throw e
    // ignorar stat warning
  }
  if (!transcriptionPath || !transcriptionPath.trim()) {
    // Transcripción puede venir de transcript BD pero Express la requiere como archivo — validar
    console.warn(`[engine:express] transcriptionPath vacío — verificar video.transcription_filepath`)
    throw new Error(`Transcripción no encontrada: transcriptionPath vacío para video ${videoPath}`)
  }
  if (!fs.existsSync(transcriptionPath)) {
    throw new Error(`Transcripción no encontrada en disco: ${transcriptionPath}`)
  }
  const provider = getProvider()
  console.log(`[engine:express] provider=${provider} ANTHROPIC=${!!process.env.ANTHROPIC_API_KEY} OPENAI=${!!process.env.OPENAI_API_KEY} OPENROUTER=${!!process.env.OPENROUTER_API_KEY}`)
  // Try real Python engine via child_process (soporta ANTHROPIC_API_KEY/OPENAI_API_KEY/OPENROUTER_API_KEY/DEEPSEEK)
  try {
    const { spawnSync } = await import('child_process')
    const path = await import('path')
    const root = path.resolve(process.cwd(), '..')
    const enginePath = path.join(root, 'engine.py')
    if (fs.existsSync(enginePath)) {
      const env = { ...process.env }
      const res = spawnSync('python', [enginePath, videoPath, transcriptionPath, '--json'], { timeout: 20000, encoding: 'utf-8', env })
      if (res.status === 0 && res.stdout) {
        try {
          const parsed = JSON.parse(res.stdout)
          if (parsed?.exito === false) {
            console.error(`[engine:express] engine exito=false tipo=${parsed.error_tipo} err=${parsed.error}`)
            throw new Error(parsed.error || 'engine falló')
          }
          if (parsed?.clips && Array.isArray(parsed.clips) && parsed.clips.length > 0) {
            console.log(`[engine:express] engine real OK ${parsed.clips.length} clips`)
            return { clips: parsed.clips, engine: 'real', provider }
          }
          if (parsed?.clips) return { clips: parsed.clips, engine: 'real', provider }
        } catch (e) {
          console.error('[engine:express] parse engine JSON fallo', e)
        }
      } else {
        const stderr = (res.stderr as unknown as string) || String(res.error || '') || ''
        const stdout = (res.stdout as unknown as string) || ''
        console.error(`[engine:express] spawn fallo status=${res.status} stderr=${String(stderr).slice(0, 800)} stdout=${String(stdout).slice(0,500)}`)
        // Propagar error descriptivo en lugar de solo código "4"
        const detail = stderr.trim() ? stderr.trim().slice(0, 800) : stdout.trim() ? stdout.trim().slice(0,800) : `exit code ${res.status}`
        throw new Error(`FFmpeg/engine spawn falló (code=${res.status}): ${detail}`)
      }
    } else {
      throw new Error(`engine.py no encontrado en ${enginePath} — verificar despliegue`)
    }
  } catch (e) {
    console.error('[engine:express] spawn exception', e, e instanceof Error ? e.stack : '')
    if (e instanceof Error && (e.message.includes('spawn falló') || e.message.includes('engine.py no encontrado'))) throw e
  }
  // Intento directo Anthropic/OpenRouter si python falló y hay key — log con traceback
  if (provider !== 'none') {
    try {
      console.log(`[engine:express] intento LLM directo provider=${provider} no implementado full`)
    } catch (e) {
      console.error('[engine:express] LLM directo fallo', e, e instanceof Error ? e.stack : '')
    }
  }
  // Modo 100% real — sin fallback de prueba. Error descriptivo con causa raíz
  throw new Error(`Engine real no disponible o falló — verificar ANTHROPIC_API_KEY, engine.py y que video/transcripción existan (provider=${provider}). Revisar logs spawn previos para código de salida.`)
}

function buildFallback(_videoId: string, _preview: string): Record<string, unknown> {
  // Deshabilitado en modo 100% real — no genera clips sintéticos
  throw new Error('buildFallback deshabilitado en modo 100% real')
}

async function runJob(jobId: string): Promise<void> {
  const client = await pool.connect()
  try {
    await client.query("UPDATE jobs SET status = 'processing', updated_at = NOW() WHERE id = $1", [jobId])
    const jobRes = await client.query('SELECT video_id FROM jobs WHERE id = $1', [jobId])
    if (jobRes.rows.length === 0) return
    const videoId = jobRes.rows[0].video_id as string
    const videoRes = await client.query('SELECT file_path, transcription_filepath, transcript FROM videos WHERE id = $1', [videoId])
    if (videoRes.rows.length === 0) throw new Error('Video asociado no encontrado')
    const video = videoRes.rows[0] as Record<string, unknown>
    const videoPath = video.file_path as string
    const transcriptionPath = (video.transcription_filepath as string) || ''

    // Modo 100% real — sin fallback, error se propaga a FAILED
    const result: Record<string, unknown> = await runClipEngine(videoPath, transcriptionPath)

    let clipsPayload: Record<string, unknown>[] = Array.isArray((result as Record<string, unknown>).clips)
      ? ((result as Record<string, unknown>).clips as Record<string, unknown>[])
      : Array.isArray(result)
        ? (result as unknown as Record<string, unknown>[])
        : []

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
      if (typeof item !== 'object' || item === null) continue
      const title = (item.title as string) || (item.titulo as string) || (item.titulo_sugerido as string) || 'Clip'
      const startRaw = (item.start_time as unknown) ?? (item.inicio as unknown) ?? 0
      const endRaw = (item.end_time as unknown) ?? (item.fin as unknown) ?? 10
      let start = parseTimeToSeconds(startRaw)
      let end = parseTimeToSeconds(endRaw)
      if (end <= start) end = start + 30
      const score = item.score !== undefined && item.score !== null ? Number(item.score) : null
      const tags = Array.isArray(item.tags) ? item.tags : item.tags ? [String(item.tags)] : null
      const storage = (item.storage_path as string) || (item.file_path as string) || ''
      await client.query(
        'INSERT INTO clips (video_id, job_id, title, start_time, end_time, score, tags, file_path, status) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)',
        [videoId, jobId, String(title).slice(0, 255), start, end, score, tags ? JSON.stringify(tags) : null, storage, 'ready']
      )
    }
    console.log(`[jobs:express] job ${jobId} completado 100% real ${clipsPayload.length} clips`)
  } catch (err: unknown) {
    // FIX: Capturar e imprimir Traceback completo en lugar de solo str(err) == "4"
    const stack = err instanceof Error ? err.stack ?? '' : ''
    console.error(`[jobs:express] fallo irrecuperable job=${jobId} — modo 100% real sin fallback`, err, stack ? `\nStack: ${stack}` : '')
    let rawMsg = err instanceof Error ? String(err.message).trim() : String(err).trim()
    let descriptive = rawMsg
    if (!rawMsg || rawMsg === '4' || rawMsg.length <= 4) {
      descriptive = `${err instanceof Error ? err.name : 'Error'}: ${rawMsg || 'error sin mensaje'} — Fallo en pipeline Job ${jobId}. Posibles causas: segments vacío (Whisper sin audio), filepath no existe, o FFmpeg args inválidos. Stack: ${stack.slice(0,1500)}`
    } else {
      descriptive = `${err instanceof Error ? err.name + ': ' : ''}${rawMsg}${stack ? `\n${stack.slice(0,1200)}` : ''}`
    }
    if (stack.includes('segments') && (stack.includes('RangeError') || stack.includes('index') || rawMsg.includes('index'))) {
      descriptive = `No se detectaron segmentos de audio suficientes en el video — Whisper devolvió lista vacía. Job ${jobId}: ${rawMsg}${stack ? `\n${stack.slice(0,1200)}` : ''}`
    }
    // Validación de arrays vacíos: mensaje descriptivo si clips vacíos
    if (rawMsg.includes('0 clips') || rawMsg.includes('no devolvió clips')) {
      descriptive = `No se detectaron segmentos de audio suficientes en el video — engine devolvió 0 clips. Job ${jobId}: verificar transcripción y audio. ${rawMsg}`
    }
    try {
      const tbMeta = JSON.stringify({ error: descriptive.slice(0,2000), error_type: err instanceof Error ? err.name : 'Unknown', traceback: stack.slice(0,3000), engine: 'real', failed: true })
      await pool.query("UPDATE jobs SET status = 'failed', error_message = $1, result_metadata = $2::jsonb, updated_at = NOW() WHERE id = $3", [descriptive.slice(0, 2000), tbMeta, jobId])
      console.info(`[jobs:express] job ${jobId} marcado FAILED con mensaje descriptivo`)
    } catch (dbErr) {
      console.error(`[jobs:express] error al marcar FAILED job=${jobId}`, dbErr)
    }
  } finally {
    client.release()
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
    if (vRes.rows.length === 0) return res.status(404).json({ detail: 'Video no encontrado' })
    if (String(vRes.rows[0].usuario_id) !== String(userId)) return res.status(403).json({ detail: 'No autorizado para este video' })

    const jRes = await client.query("INSERT INTO jobs (video_id, status) VALUES ($1,'pending') RETURNING id, video_id, status, error_message, result_metadata, created_at, updated_at", [videoId])
    const job = jRes.rows[0] as Record<string, unknown>
    const jobId = String(job.id)
    setImmediate(() => {
      runJob(jobId).catch((e) => console.error('runJob error', e))
    })
    return res.status(202).json({
      id: job.id,
      video_id: job.video_id,
      status: String(job.status).toUpperCase(),
      error_message: job.error_message ?? null,
      result_metadata: job.result_metadata ?? null,
      created_at: new Date(job.created_at as string).toISOString(),
      updated_at: new Date(job.updated_at as string).toISOString(),
    })
  } catch (err) {
    console.error('POST /videos/:videoId/jobs error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

jobsRouter.get('/jobs/:jobId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const jobId = String(req.params.jobId)
  if (!isValidUuid(jobId)) return res.status(422).json({ detail: 'job_id debe ser UUID válido' })
  try {
    const jRes = await pool.query('SELECT j.id, j.video_id, j.status, j.error_message, j.result_metadata, j.created_at, j.updated_at, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1', [jobId])
    if (jRes.rows.length === 0) return res.status(404).json({ detail: 'Job no encontrado' })
    const row = jRes.rows[0] as Record<string, unknown>
    if (String(row.usuario_id) !== String(userId)) return res.status(404).json({ detail: 'Job no encontrado' })
    return res.json({
      id: row.id,
      video_id: row.video_id,
      status: String(row.status).toUpperCase(),
      error_message: row.error_message ?? null,
      result_metadata: row.result_metadata ?? null,
      created_at: new Date(row.created_at as string).toISOString(),
      updated_at: new Date(row.updated_at as string).toISOString(),
    })
  } catch (err) {
    console.error('GET /jobs/:jobId error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})

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

  const STATUS_MAP: Record<string, { progress: number; status: string; message: string }> = {
    pending: { progress: 0, status: 'pending', message: 'En cola' },
    processing: { progress: 55, status: 'scoring', message: 'Procesando con IA' },
    completed: { progress: 100, status: 'completed', message: 'Completado' },
    failed: { progress: 100, status: 'failed', message: 'Falló' },
  }

  let lastStatus: string | null = null
  const interval = setInterval(async () => {
    try {
      const r = await pool.query('SELECT j.status, j.error_message, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1', [jobId])
      if (r.rows.length === 0) {
        res.write(`event: error\ndata: ${JSON.stringify({ detail: 'Job no encontrado' })}\n\n`)
        clearInterval(interval)
        res.end()
        return
      }
      const row = r.rows[0] as Record<string, unknown>
      if (String(row.usuario_id) !== String(userId)) {
        res.write(`event: error\ndata: ${JSON.stringify({ detail: 'No autorizado' })}\n\n`)
        clearInterval(interval)
        res.end()
        return
      }
      const raw = String(row.status)
      if (raw === lastStatus) return
      lastStatus = raw
      const mapped = STATUS_MAP[raw.toLowerCase()] ?? { progress: 0, status: raw, message: raw }
      const payload: Record<string, unknown> = { progress: mapped.progress, status: mapped.status, message: mapped.message, job_id: jobId }
      if (row.error_message) payload.error = row.error_message
      res.write(`data: ${JSON.stringify(payload)}\n\n`)
      if (raw.toLowerCase() === 'completed' || raw.toLowerCase() === 'failed') {
        res.write('event: done\ndata: {}\n\n')
        clearInterval(interval)
        res.end()
      }
    } catch (e) {
      console.error('SSE stream error', e)
      clearInterval(interval)
      res.end()
    }
  }, 1000)

  req.on('close', () => {
    clearInterval(interval)
  })
})
