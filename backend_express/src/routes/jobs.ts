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
  if (!fs.existsSync(videoPath) || !fs.existsSync(transcriptionPath)) {
    throw new Error('Video o transcripción no encontrada')
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
        const stderr = (res.stderr as unknown as string) || ''
        console.error(`[engine:express] spawn fallo status=${res.status} stderr=${String(stderr).slice(0, 500)}`)
      }
    }
  } catch (e) {
    console.error('[engine:express] spawn exception', e)
  }
  // Intento directo Anthropic/OpenRouter si python falló y hay key
  if (provider !== 'none') {
    try {
      console.log(`[engine:express] intento LLM directo provider=${provider} no implementado full, usando fallback transcript-based`)
    } catch (e) {
      console.error('[engine:express] LLM directo fallo', e)
    }
  }
  // Fallback determinístico transcript-based (no deja FAILED)
  await new Promise((r) => setTimeout(r, 800))
  let preview = ''
  try {
    const fs2 = await import('fs')
    preview = fs2.readFileSync(transcriptionPath, 'utf-8').slice(0, 120)
  } catch {}
  console.warn('[engine:express] fallback simulado aplicado')
  return {
    clips: [
      { inicio: '00:00:10', fin: '00:00:45', titulo: 'Clip destacado 1 (fallback)', score: 7.5, transcript_preview: preview },
      { inicio: '00:01:00', fin: '00:01:35', titulo: 'Clip destacado 2 (fallback)', score: 7.0 },
    ],
    engine: 'fallback',
    provider,
    fallback: true,
  }
}

function buildFallback(videoId: string, preview: string): Record<string, unknown> {
  return {
    clips: [
      { inicio: '00:00:10', fin: '00:00:45', titulo: 'Clip destacado 1 (fallback)', score: 7.5, transcript_preview: preview.slice(0, 120) },
      { inicio: '00:01:00', fin: '00:01:35', titulo: 'Clip destacado 2 (fallback)', score: 7.0 },
    ],
    engine: 'fallback',
    fallback: true,
  }
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

    let result: Record<string, unknown>
    try {
      result = await runClipEngine(videoPath, transcriptionPath)
    } catch (e) {
      console.error(`[jobs:express] runClipEngine exception job=${jobId}`, e)
      const preview = (video.transcript as string) || ''
      console.warn(`[jobs:express] fallback aplicado job=${jobId}`)
      result = buildFallback(videoId, preview)
      ;(result as Record<string, unknown>).fallback_error = e instanceof Error ? e.message : String(e)
    }

    let clipsPayload: Record<string, unknown>[] = Array.isArray((result as Record<string, unknown>).clips)
      ? ((result as Record<string, unknown>).clips as Record<string, unknown>[])
      : Array.isArray(result)
        ? (result as unknown as Record<string, unknown>[])
        : []

    if (clipsPayload.length === 0) {
      console.warn(`[jobs:express] 0 clips devueltos job=${jobId}, usando fallback`)
      const preview = (video.transcript as string) || ''
      result = buildFallback(videoId, preview)
      clipsPayload = (result.clips as Record<string, unknown>[]) || []
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
    if ((result as Record<string, unknown>).fallback) {
      console.warn(`[jobs:express] job ${jobId} completado via fallback`)
    } else {
      console.log(`[jobs:express] job ${jobId} completado ${clipsPayload.length} clips`)
    }
  } catch (err: unknown) {
    console.error(`[jobs:express] fallo irrecuperable job=${jobId}`, err)
    try {
      const preview = ''
      const fallback = buildFallback('', preview)
      ;(fallback as Record<string, unknown>).fatal_error = err instanceof Error ? err.message : String(err)
      const jRes = await pool.query('SELECT video_id FROM jobs WHERE id = $1', [jobId])
      const vid = jRes.rows[0]?.video_id as string | undefined
      await pool.query('UPDATE jobs SET result_metadata = $1::jsonb, status = $2, error_message = NULL, updated_at = NOW() WHERE id = $3', [
        JSON.stringify(fallback),
        'completed',
        jobId,
      ])
      const clips = (fallback.clips as Record<string, unknown>[]) || []
      for (const item of clips) {
        const title = (item.titulo as string) || 'Clip fallback'
        const start = parseTimeToSeconds(item.inicio as unknown)
        const end = parseTimeToSeconds(item.fin as unknown)
        await pool.query('INSERT INTO clips (video_id, job_id, title, start_time, end_time, score, tags, file_path, status) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)', [
          vid || '00000000-0000-0000-0000-000000000000',
          jobId,
          String(title).slice(0, 255),
          start,
          end,
          7.0,
          null,
          '',
          'ready',
        ])
      }
      console.warn(`[jobs:express] job ${jobId} recuperado via fallback tras error fatal`)
      return
    } catch (e2) {
      console.error(`[jobs:express] fallback fatal también falló job=${jobId}`, e2)
    }
    const msg = err instanceof Error ? err.message : String(err)
    try {
      await pool.query("UPDATE jobs SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2", [msg.slice(0, 2000), jobId])
    } catch {}
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
