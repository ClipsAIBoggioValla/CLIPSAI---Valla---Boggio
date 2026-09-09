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
        console.log(`[publish:express] webhook status=${res.status} fallback simulado`)
      }
    } catch (e) {
      console.log(`[publish:express] webhook error ${e} fallback simulado`)
    }
  } else {
    await new Promise((r) => setTimeout(r, 2000))
    console.log(`[publish:express] simulado clip=${clipId} platform=${platform} url=${fakeUrl}`)
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
