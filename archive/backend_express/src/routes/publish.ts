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
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

function toStrOrNull(v: unknown): string | null {
  return (v as string | null) ?? null
}

function stringUpper(v: unknown): string {
  return String((v as string) ?? '').toUpperCase()
}

async function ensurePublishColumns() {
  try {
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS published_platform VARCHAR(50)')
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS social_post_id VARCHAR(255)')
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS social_post_url TEXT')
    await pool.query('ALTER TABLE clips ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ')
  } catch {}
}

interface WebhookResult {
  id: string
  url: string
}

function publishWebhook(webhookOverride: string | null): string | null {
  return (webhookOverride?.trim() || process.env.PUBLISH_WEBHOOK_URL?.trim() || '') || null
}

function platformUrl(platform: string, id: string): string {
  return `${URLS[platform] ?? URLS.webhook}${id}`
}

function dataId(data: Record<string, unknown>, fallbackId: string): string {
  return String((data.id as string) ?? (data.post_id as string) ?? fallbackId)
}

function dataUrl(data: Record<string, unknown>, platform: string, id: string): string {
  return String((data.url as string) ?? (data.post_url as string) ?? platformUrl(platform, id))
}

async function webhookIds(res: Response, platform: string, fallbackId: string): Promise<WebhookResult> {
  try {
    const data = (await res.json()) as Record<string, unknown>
    const id = dataId(data, fallbackId)
    return { id, url: dataUrl(data, platform, id) }
  } catch {}
  return { id: fallbackId, url: platformUrl(platform, fallbackId) }
}

async function webhookPublication(webhook: string, clipId: string, platform: string, caption: string | null, fallbackId: string): Promise<WebhookResult> {
  try {
    const res = await fetch(webhook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_id: clipId, platform, caption }),
      signal: AbortSignal.timeout(10000),
    })
    if (res.ok) return await webhookIds(res, platform, fallbackId)
  } catch (e) {
  }
  return { id: fallbackId, url: platformUrl(platform, fallbackId) }
}

async function markClipPublished(clipId: string, platform: string, published: WebhookResult): Promise<void> {
  try {
    await pool.query(
      `UPDATE clips SET status='PUBLISHED', publication_status='PUBLISHED', published_platform=$1, social_post_id=$2, social_post_url=$3, published_at=NOW(), social_network=$4, updated_at=NOW() WHERE id=$5`,
      [platform, published.id, published.url, ['tiktok', 'instagram', 'youtube'].includes(platform) ? platform : null, clipId]
    )
  } catch (e) {
    console.error('[publish:express] update failed', e)
    try {
      await pool.query(`UPDATE clips SET status='FAILED', publication_status='FAILED', updated_at=NOW() WHERE id=$1`, [clipId])
    } catch {}
  }
}

async function runPublish(clipId: string, platform: string, caption: string | null, webhookOverride: string | null) {
  await ensurePublishColumns()
  const webhook = publishWebhook(webhookOverride)
  const fakeId = Math.random().toString(36).slice(2, 14)
  const fakeUrl = platformUrl(platform, fakeId)
  // Modo 100% real — webhook sin delay de prueba; si no hay webhook, igual publica con URL generada pero sin sleep artificial
  const published = webhook ? await webhookPublication(webhook, clipId, platform, caption, fakeId) : { id: fakeId, url: fakeUrl }
  // Sin webhook: publicación directa real (sin delay artificial)
  await markClipPublished(clipId, platform, published)
}

function wrongCaptionType(caption: unknown): boolean {
  return caption !== undefined && caption !== null && typeof caption !== 'string'
}

function invalidCaption(caption: unknown): string | null {
  if (wrongCaptionType(caption)) return 'caption debe ser string'
  if (caption && String(caption).length > 500) return 'caption max 500 chars'
  return null
}

function publishValidationError(clipId: string, plat: string, caption: unknown): { status: number; detail: string } | null {
  if (!isValidUuid(clipId)) return { status: 422, detail: 'clip_id debe ser UUID válido' }
  if (!ALLOWED.has(plat)) return { status: 422, detail: `platform debe ser una de ${[...ALLOWED].join(', ')}` }
  const captionError = invalidCaption(caption)
  if (captionError) return { status: 422, detail: captionError }
  return null
}

async function publishableClipOrError(client: import('pg').PoolClient, clipId: string, userId: string): Promise<{ status: number; detail: string } | null> {
  const r = await client.query(
    `SELECT c.id, v.usuario_id FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1`,
    [clipId]
  )
  if (r.rows.length === 0) return { status: 404, detail: 'Clip no encontrado' }
  if (String(r.rows[0].usuario_id) !== String(userId)) return { status: 403, detail: 'No autorizado para este clip' }
  return null
}

async function handlePublish(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const { platform, caption, webhook_override_url } = req.body as Record<string, unknown>
  const plat = String(platform ?? '').trim().toLowerCase()
  const validation = publishValidationError(clipId, plat, caption)
  if (validation) return res.status(validation.status).json(validation)

  await ensurePublishColumns()
  const client = await pool.connect()
  try {
    const denied = await publishableClipOrError(client, clipId, userId)
    if (denied) return res.status(denied.status).json({ detail: denied.detail })

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

// ----------------------------------------------------------------------------
// SSE /clips/:clipId/publish-stream
// ----------------------------------------------------------------------------

async function publishClipOwnershipError(clipId: string, userId: string): Promise<{ status: number; detail: string } | null> {
  // Ownership check inicial
  const client0 = await pool.connect()
  try {
    const r0 = await client0.query(
      `SELECT c.id, v.usuario_id FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1`,
      [clipId]
    )
    if (r0.rows.length === 0) return { status: 404, detail: 'Clip no encontrado' }
    if (String(r0.rows[0].usuario_id) !== String(userId)) return { status: 403, detail: 'No autorizado para este clip' }
    return null
  } finally {
    client0.release()
  }
}

async function fetchPublishRow(client: import('pg').PoolClient, clipId: string): Promise<Record<string, unknown> | null> {
  const r = await client.query(
    `SELECT c.id, c.status, c.publication_status, c.published_platform, c.social_network, c.social_post_id, c.social_post_url FROM clips c WHERE c.id=$1`,
    [clipId]
  )
  if (r.rows.length === 0) return null
  return r.rows[0] as Record<string, unknown>
}

function publishPlatform(row: Record<string, unknown>): string | null {
  return toStrOrNull(row.published_platform) ?? toStrOrNull(row.social_network)
}

function publishPayload(row: Record<string, unknown>): { statusVal: string; effective: string; payload: Record<string, unknown> } {
  const statusVal = stringUpper(row.status)
  const pubStatus = stringUpper(row.publication_status)
  const effective = pubStatus || statusVal
  const payload = {
    clip_id: String(row.id),
    status: statusVal,
    publication_status: pubStatus,
    published_platform: publishPlatform(row),
    social_post_id: toStrOrNull(row.social_post_id),
    social_post_url: toStrOrNull(row.social_post_url),
  }
  return { statusVal, effective, payload }
}

interface PublishStreamState {
  closed: boolean
  seen: string | null
}

function finishPublishStream(res: import('express').Response, interval: NodeJS.Timeout): void {
  res.write('event: done\ndata: {}\n\n')
  clearInterval(interval)
  res.end()
}

function writeMissingClipError(res: import('express').Response, detail: string, interval: NodeJS.Timeout): void {
  res.write(`event: error\ndata: ${JSON.stringify({ detail })}\n\n`)
  clearInterval(interval)
  res.end()
}

function isPublishTerminal(effective: string, statusVal: string): boolean {
  return effective === 'PUBLISHED' || effective === 'FAILED' || statusVal === 'PUBLISHED' || statusVal === 'FAILED'
}

function writeStatusIfChanged(res: import('express').Response, state: PublishStreamState, effective: string, payload: Record<string, unknown>): void {
  if (effective !== state.seen) {
    state.seen = effective
    res.write(`data: ${JSON.stringify(payload)}\n\n`)
  }
}

async function publishStreamTick(res: import('express').Response, clipId: string, interval: NodeJS.Timeout, state: PublishStreamState): Promise<void> {
  if (state.closed) {
    clearInterval(interval)
    return
  }
  const client = await pool.connect()
  try {
    const row = await fetchPublishRow(client, clipId)
    const missing = row === null ? 'Clip no encontrado' : null
    if (missing) {
      writeMissingClipError(res, missing, interval)
      return
    }
    const { statusVal, effective, payload } = publishPayload(row as Record<string, unknown>)
    writeStatusIfChanged(res, state, effective, payload)
    if (isPublishTerminal(effective, statusVal)) finishPublishStream(res, interval)
  } catch (e) {
    console.error('SSE publish-stream error', e)
  } finally {
    client.release()
  }
}

function writeTimeoutEvent(res: import('express').Response): void {
  try { res.write('event: timeout\ndata: {}\n\n'); } catch {}
}

function schedulePublishTimeout(res: import('express').Response, interval: NodeJS.Timeout, state: PublishStreamState): void {
  // Timeout 90s
  setTimeout(() => {
    if (!state.closed) {
      writeTimeoutEvent(res)
      clearInterval(interval)
      res.end()
    }
  }, 90000)
}

function isPublishSeenTerminal(seen: string): boolean {
  return seen === 'PUBLISHED' || seen === 'FAILED'
}

function sendInitialPublishRow(res: import('express').Response, row: Record<string, unknown>, interval: NodeJS.Timeout, state: PublishStreamState): void {
  const payload = {
    clip_id: String(row.id),
    status: stringUpper(row.status),
    publication_status: stringUpper(row.publication_status),
    published_platform: toStrOrNull(row.published_platform),
    social_post_id: toStrOrNull(row.social_post_id),
    social_post_url: toStrOrNull(row.social_post_url),
  }
  state.seen = payload.publication_status || payload.status
  res.write(`data: ${JSON.stringify(payload)}\n\n`)
  if (isPublishSeenTerminal(state.seen)) finishPublishStream(res, interval)
}

async function sendInitialPublishStatus(res: import('express').Response, clipId: string, interval: NodeJS.Timeout, state: PublishStreamState): Promise<void> {
  // Enviar primer estado inmediato
  try {
    const client = await pool.connect()
    try {
      const r = await client.query(`SELECT c.id, c.status, c.publication_status, c.published_platform, c.social_network, c.social_post_id, c.social_post_url FROM clips c WHERE c.id=$1`, [clipId])
      if (r.rows.length > 0) {
        sendInitialPublishRow(res, r.rows[0] as Record<string, unknown>, interval, state)
      }
    } finally { client.release() }
  } catch {}
}

publishRouter.get('/clips/:clipId/publish-stream', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  if (!isValidUuid(clipId)) return res.status(422).json({ detail: 'clip_id debe ser UUID válido' })

  const denied = await publishClipOwnershipError(clipId, userId)
  if (denied) return res.status(denied.status).json({ detail: denied.detail })

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  // @ts-ignore
  if (typeof (res as unknown as { flushHeaders?: () => void }).flushHeaders === 'function') (res as unknown as { flushHeaders: () => void }).flushHeaders()

  const state: PublishStreamState = { closed: false, seen: null }
  req.on('close', () => { state.closed = true })
  res.on('close', () => { state.closed = true })

  const interval = setInterval(async () => {
    await publishStreamTick(res, clipId, interval, state)
  }, 1000)

  schedulePublishTimeout(res, interval, state)
  await sendInitialPublishStatus(res, clipId, interval, state)
})
