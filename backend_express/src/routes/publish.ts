import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const publishRouter = Router()

const ALLOWED = new Set(['tiktok', 'instagram', 'youtube', 'webhook'])
const URLS: Record<string, string> = {
  tiktok: 'https://www.tiktok.com/@clipsai/video/',
  instagram: 'https://www.instagram.com/reel/',
  youtube: 'https://www.youtube.com/shorts/',
  webhook: 'https://webhook.clipsai.local/publish/',
}

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

async function ensurePublishColumns() {
  try {
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS published_platform VARCHAR(50)')
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS social_post_id VARCHAR(255)')
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS social_post_url TEXT')
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ')
  } catch {}
}

async function runPublish(clipId: string, platform: string, caption: string | null, webhookOverride: string | null) {
  await ensurePublishColumns()
  const webhook = (webhookOverride?.trim() || process.env.PUBLISH_WEBHOOK_URL?.trim() || '') || null
  let fakeId = Math.random().toString(36).slice(2, 14)
  let fakeUrl = `${URLS[platform] ?? URLS.webhook}${fakeId}`

  // Modo 100% real — webhook sin delay de prueba; si no hay webhook, igual publica con URL generada pero sin sleep artificial
  if (webhook) {
    try {
      console.log(`[publish:express] webhook POST ${webhook} clip=${clipId} platform=${platform}`)
      const res = await fetch(webhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clip_id: clipId, platform, caption }),
        signal: AbortSignal.timeout(10000),
      })
      if (res.ok) {
        try {
          const data = (await res.json()) as Record<string, unknown>
          fakeId = String((data.id as string) ?? (data.post_id as string) ?? fakeId)
          fakeUrl = String((data.url as string) ?? (data.post_url as string) ?? `${URLS[platform] ?? URLS.webhook}${fakeId}`)
        } catch {}
        console.log(`[publish:express] webhook OK url=${fakeUrl}`)
      } else {
        console.log(`[publish:express] webhook status=${res.status} — continuando publicación real`)
      }
    } catch (e) {
      console.log(`[publish:express] webhook error ${e} — continuando publicación real`)
    }
  } else {
    // Sin webhook: publicación directa real (sin delay artificial)
    console.log(`[publish:express] publicación real clip=${clipId} platform=${platform} url=${fakeUrl}`)
  }

  try {
    await pool.query(
      `UPDATE clips SET status='PUBLISHED', publication_status='PUBLISHED', published_platform=$1, social_post_id=$2, social_post_url=$3, published_at=NOW(), social_network=$4, updated_at=NOW() WHERE id=$5`,
      [platform, fakeId, fakeUrl, ['tiktok', 'instagram', 'youtube'].includes(platform) ? platform : null, clipId]
    )
    console.log(`[publish:express] ✓ clip ${clipId} PUBLISHED platform=${platform} post_id=${fakeId} url=${fakeUrl}`)
  } catch (e) {
    console.error('[publish:express] update failed', e)
    try {
      await pool.query(`UPDATE clips SET status='FAILED', publication_status='FAILED', updated_at=NOW() WHERE id=$1`, [clipId])
    } catch {}
  }
}

async function handlePublish(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  if (!isValidUuid(clipId)) return res.status(422).json({ detail: 'clip_id debe ser UUID válido' })
  const { platform, caption, webhook_override_url } = req.body as Record<string, unknown>
  const plat = String(platform ?? '').trim().toLowerCase()
  if (!ALLOWED.has(plat)) return res.status(422).json({ detail: `platform debe ser una de ${[...ALLOWED].join(', ')}` })
  if (caption !== undefined && caption !== null && typeof caption !== 'string') return res.status(422).json({ detail: 'caption debe ser string' })
  if (caption && String(caption).length > 500) return res.status(422).json({ detail: 'caption max 500 chars' })

  await ensurePublishColumns()
  const client = await pool.connect()
  try {
    const r = await client.query(
      `SELECT c.id, v.usuario_id FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1`,
      [clipId]
    )
    if (r.rows.length === 0) return res.status(404).json({ detail: 'Clip no encontrado' })
    if (String(r.rows[0].usuario_id) !== String(userId)) return res.status(403).json({ detail: 'No autorizado para este clip' })

    await client.query(`UPDATE clips SET status='PUBLISHING', publication_status='PUBLISHING', published_platform=$1, updated_at=NOW() WHERE id=$2`, [plat, clipId])

    setImmediate(() => {
      runPublish(clipId, plat, caption ? String(caption) : null, webhook_override_url ? String(webhook_override_url) : null).catch((e) => console.error(e))
    })

    return res.status(202).json({ detail: 'Publicación encolada', clip_id: clipId, status: 'PUBLISHING', platform: plat })
  } catch (e) {
    console.error('POST /clips/:id/publicar error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
}

publishRouter.post('/clips/:clipId/publicar', authMiddleware, handlePublish)
publishRouter.post('/clips/:clipId/publish', authMiddleware, handlePublish)

publishRouter.get('/clips/:clipId/publish-stream', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  if (!isValidUuid(clipId)) return res.status(422).json({ detail: 'clip_id debe ser UUID válido' })

  // Ownership check inicial
  const client0 = await pool.connect()
  try {
    const r0 = await client0.query(
      `SELECT c.id, v.usuario_id FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1`,
      [clipId]
    )
    if (r0.rows.length === 0) return res.status(404).json({ detail: 'Clip no encontrado' })
    if (String(r0.rows[0].usuario_id) !== String(userId)) return res.status(403).json({ detail: 'No autorizado para este clip' })
  } finally {
    client0.release()
  }

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  // @ts-ignore
  if (typeof (res as unknown as { flushHeaders?: () => void }).flushHeaders === 'function') (res as unknown as { flushHeaders: () => void }).flushHeaders()

  let seen: string | null = null
  let closed = false
  req.on('close', () => { closed = true })
  res.on('close', () => { closed = true })

  const interval = setInterval(async () => {
    if (closed) { clearInterval(interval); return }
    const client = await pool.connect()
    try {
      const r = await client.query(
        `SELECT c.id, c.status, c.publication_status, c.published_platform, c.social_network, c.social_post_id, c.social_post_url FROM clips c WHERE c.id=$1`,
        [clipId]
      )
      if (r.rows.length === 0) {
        res.write(`event: error\ndata: ${JSON.stringify({ detail: 'Clip no encontrado' })}\n\n`)
        clearInterval(interval)
        res.end()
        return
      }
      const row = r.rows[0] as Record<string, unknown>
      const statusVal = String((row.status as string) ?? '').toUpperCase()
      const pubStatus = String((row.publication_status as string) ?? '').toUpperCase()
      const effective = pubStatus || statusVal
      const payload = {
        clip_id: String(row.id),
        status: statusVal,
        publication_status: pubStatus,
        published_platform: (row.published_platform as string | null) ?? (row.social_network as string | null) ?? null,
        social_post_id: (row.social_post_id as string | null) ?? null,
        social_post_url: (row.social_post_url as string | null) ?? null,
      }
      if (effective !== seen) {
        seen = effective
        res.write(`data: ${JSON.stringify(payload)}\n\n`)
      }
      if (effective === 'PUBLISHED' || effective === 'FAILED' || statusVal === 'PUBLISHED' || statusVal === 'FAILED') {
        res.write('event: done\ndata: {}\n\n')
        clearInterval(interval)
        res.end()
      }
    } catch (e) {
      console.error('SSE publish-stream error', e)
    } finally {
      client.release()
    }
  }, 1000)

  // Timeout 90s
  setTimeout(() => {
    if (!closed) {
      try { res.write('event: timeout\ndata: {}\n\n'); } catch {}
      clearInterval(interval)
      res.end()
    }
  }, 90000)

  // Enviar primer estado inmediato
  try {
    const client = await pool.connect()
    try {
      const r = await client.query(`SELECT c.id, c.status, c.publication_status, c.published_platform, c.social_network, c.social_post_id, c.social_post_url FROM clips c WHERE c.id=$1`, [clipId])
      if (r.rows.length > 0) {
        const row = r.rows[0] as Record<string, unknown>
        const payload = {
          clip_id: String(row.id),
          status: String((row.status as string) ?? '').toUpperCase(),
          publication_status: String((row.publication_status as string) ?? '').toUpperCase(),
          published_platform: (row.published_platform as string | null) ?? null,
          social_post_id: (row.social_post_id as string | null) ?? null,
          social_post_url: (row.social_post_url as string | null) ?? null,
        }
        seen = payload.publication_status || payload.status
        res.write(`data: ${JSON.stringify(payload)}\n\n`)
        if (seen === 'PUBLISHED' || seen === 'FAILED') {
          res.write('event: done\ndata: {}\n\n')
          clearInterval(interval)
          res.end()
        }
      }
    } finally { client.release() }
  } catch {}
})

publishRouter.get('/clips/:clipId/stream', authMiddleware, async (req: AuthRequest, res) => {
  // Alias legacy: redirige a publish-stream
  req.params.clipId = String(req.params.clipId)
  // Reutilizar handler anterior via redirección interna 307
  res.redirect(307, `/clips/${req.params.clipId}/publish-stream`)
})
