import { Router, Request, Response } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'
import crypto from 'crypto'

export const socialAuthRouter = Router()

const ALLOWED_PLATFORMS = new Set(['youtube', 'instagram', 'tiktok'])

/** Primer valor de env no vacío (equivalente a `a || b || c || ''`). */
function firstEnv(...names: string[]): string {
  for (const name of names) {
    const value = process.env[name] || ''
    if (value) return value
  }
  return ''
}

// ============================================================================
// Helpers de config (port de youtube_service / instagram_service / tiktok_service)
// ============================================================================

function getFrontendBase(): string {
  let base = (process.env.FRONTEND_REDIRECT_URL || '').trim()
  if (!base) base = (process.env.FRONTEND_URL || '').trim()
  if (!base) base = 'http://localhost:3000'
  return base.replace(/\/+$/, '')
}

/** Fuerza api.clipsai.xyz si la URI contiene un host temporal. */
function sanitizeRedirect(uri: string, fallback: string): string {
  if (!uri) return fallback
  if (/decorator|guns-camps|ngrok|trycloudflare/.test(uri)) return fallback
  return uri
}

function publicBackendBase(): string {
  return (process.env.PUBLIC_BACKEND_URL || 'https://api.clipsai.xyz').replace(/\/+$/, '')
}

function socialRedirectUri(envName: string, defaultUri: string): string {
  return sanitizeRedirect((process.env[envName] || '').trim() || defaultUri, defaultUri)
}

function getGoogleConfig(): { clientId: string; clientSecret: string; redirectUri: string } {
  const clientId = firstEnv('GOOGLE_CLIENT_ID').trim()
  const clientSecret = firstEnv('GOOGLE_CLIENT_SECRET').trim()
  const defaultUri = `${publicBackendBase()}/auth/social/youtube/callback`
  const redirectUri = socialRedirectUri('GOOGLE_REDIRECT_URI', defaultUri)
  return { clientId, clientSecret, redirectUri }
}

function getInstagramConfig(): { clientId: string; clientSecret: string; redirectUri: string } {
  const clientId = firstEnv('INSTAGRAM_CLIENT_ID', 'META_APP_ID', 'FB_CLIENT_ID').trim()
  const clientSecret = firstEnv('INSTAGRAM_CLIENT_SECRET', 'META_APP_SECRET', 'FB_CLIENT_SECRET').trim()
  const defaultUri = `${publicBackendBase()}/auth/social/instagram/callback`
  const redirectUri = socialRedirectUri('INSTAGRAM_REDIRECT_URI', defaultUri)
  return { clientId, clientSecret, redirectUri }
}

function getTiktokConfig(): { clientKey: string; clientSecret: string; redirectUri: string } {
  const clientKey = firstEnv('TIKTOK_CLIENT_KEY').trim()
  const clientSecret = firstEnv('TIKTOK_CLIENT_SECRET').trim()
  const defaultUri = `${publicBackendBase()}/auth/social/tiktok/callback`
  const redirectUri = socialRedirectUri('TIKTOK_REDIRECT_URI', defaultUri)
  return { clientKey, clientSecret, redirectUri }
}

// ============================================================================
// State encode/decode (base64url JSON { user_id, [code_verifier] })
// ============================================================================

function encodeState(payload: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(payload), 'utf-8')
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

function decodeState(state: string | undefined): Record<string, unknown> | null {
  if (!state) return null
  try {
    const padded = state + '='.repeat((4 - (state.length % 4)) % 4)
    const b64 = padded.replace(/-/g, '+').replace(/_/g, '/')
    const decoded = Buffer.from(b64, 'base64').toString('utf-8')
    const data = JSON.parse(decoded)
    if (data && typeof data === 'object') return data as Record<string, unknown>
    return null
  } catch {
    return null
  }
}

function encodeStateUserId(userId: string): string {
  return encodeState({ user_id: String(userId) })
}

/** PKCE pair (port de tiktok_service.generate_pkce_pair). */
function generatePkcePair(): { verifier: string; challenge: string } {
  const verifier = crypto.randomBytes(32).toString('base64url') // 43 chars
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url')
  return { verifier, challenge }
}

// ============================================================================
// Status / disconnect
// ============================================================================

const FALLBACK_USERNAME_RE = /^(instagram|youtube|tiktok)_[0-9a-fA-F]{8}$/
const PLATFORM_FALLBACK_NAMES: Record<string, string> = {
  instagram: 'Instagram User',
  tiktok: 'TikTok User',
}

function isFallbackUsername(username: string): boolean {
  return FALLBACK_USERNAME_RE.test(username.trim())
}

function cleanedUsername(rawUsername: unknown): string | null {
  const raw = (rawUsername as string) || null
  if (raw && isFallbackUsername(raw)) return null
  return raw
}

function normalizedUsername(platform: string, rawUsername: unknown): string | null {
  const fallbackName = PLATFORM_FALLBACK_NAMES[platform] ?? null
  return cleanedUsername(rawUsername) ?? fallbackName
}

interface StatusEntry {
  connected: true
  username: string | null
  expires_at: string | null
}

function statusEntryFor(acc: Record<string, unknown>): { platform: string; entry: StatusEntry } | null {
  const platform = String(acc.platform || '').toLowerCase()
  if (!ALLOWED_PLATFORMS.has(platform)) return null
  return {
    platform,
    entry: {
      connected: true,
      username: normalizedUsername(platform, acc.platform_username),
      expires_at: acc.token_expires_at ? new Date(acc.token_expires_at as string).toISOString() : null,
    },
  }
}

async function buildStatus(userId: string): Promise<Record<string, unknown>> {
  const status: Record<string, unknown> = {
    instagram: { connected: false, username: null, expires_at: null },
    youtube: { connected: false, username: null, expires_at: null },
    tiktok: { connected: false, username: null, expires_at: null },
  }
  try {
    const r = await pool.query(
      'SELECT platform, platform_username, token_expires_at FROM social_accounts WHERE user_id = $1',
      [userId]
    )
    for (const acc of r.rows as Array<Record<string, unknown>>) {
      const found = statusEntryFor(acc)
      if (found) status[found.platform] = found.entry
    }
  } catch (err) {
    console.error('[social/status] error:', err)
  }
  return status
}

socialAuthRouter.get('/status', authMiddleware, async (req: AuthRequest, res: Response) => {
  return res.json(await buildStatus(req.user!.id))
})

socialAuthRouter.get('/accounts', authMiddleware, async (req: AuthRequest, res: Response) => {
  return res.json(await buildStatus(req.user!.id))
})

socialAuthRouter.delete('/:platform', authMiddleware, async (req: AuthRequest, res: Response) => {
  const platformNorm = String((req.params as any).platform || '').trim().toLowerCase()
  if (!ALLOWED_PLATFORMS.has(platformNorm)) {
    return res.status(400).json({ detail: `Plataforma no válida: ${(req.params as any).platform}` })
  }
  const userId = req.user!.id
  try {
    await pool.query(
      'DELETE FROM social_accounts WHERE user_id = $1 AND lower(platform) = $2',
      [userId, platformNorm]
    )
  } catch (err) {
    console.error('[social/delete] error social_accounts:', err)
  }
  // Limpieza best-effort en tabla legacy
  try {
    await pool.query(
      'DELETE FROM user_social_accounts WHERE user_id = $1 AND lower(platform) = $2',
      [userId, platformNorm]
    )
  } catch {
    /* tabla legacy ausente: ignorar */
  }
  return res.json({ message: `Cuenta de ${platformNorm} desconectada exitosamente` })
})

// ============================================================================
// OAuth — helpers genéricos
// ============================================================================

function redirectWithIntegration(
  res: Response,
  frontendBase: string,
  integration: string,
  status: string,
  extra?: string
): void {
  const params = new URLSearchParams({ integration, status })
  if (extra) {
    params.set('error', extra)
    if (integration !== 'youtube') params.set('message', extra)
  }
  const url = `${frontendBase}/dashboard/integrations?${params.toString()}`
  res.redirect(302, url)
}

async function applyOptionalUsername(tokens: Record<string, unknown>, fetchFn: (accessToken: string) => Promise<string | null>): Promise<void> {
  try {
    const username = await fetchFn(String(tokens.access_token || ''))
    if (username) tokens.username = username
  } catch {
    /* username opcional */
  }
}

async function exchangeGoogleTokens(code: string): Promise<Record<string, unknown>> {
  const { clientId, clientSecret, redirectUri } = getGoogleConfig()
  const body = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri,
  })
  const resp = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!resp.ok) throw new Error(`Google token HTTP ${resp.status}: ${(await resp.text()).slice(0, 200)}`)
  const tokens = (await resp.json()) as Record<string, unknown>
  await applyOptionalUsername(tokens, fetchYoutubeUsername)
  return tokens
}

function youtubeSnippet(data: Record<string, unknown>): Record<string, unknown> | null {
  const items = (data.items as Array<Record<string, unknown>>) || []
  if (items.length === 0) return null
  return (items[0].snippet as Record<string, unknown>) || {}
}

function youtubeChannelName(snippet: Record<string, unknown>): string | null {
  const custom = String(snippet.customUrl || '').trim()
  if (custom) return custom
  const title = String(snippet.title || '').trim()
  return title || null
}

async function fetchYoutubeUsername(accessToken: string): Promise<string | null> {
  if (!accessToken) return null
  const url = 'https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true'
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } })
  if (resp.status !== 200) return null
  const snippet = youtubeSnippet((await resp.json()) as Record<string, unknown>)
  if (!snippet) return null
  return youtubeChannelName(snippet)
}

function youtubeRefreshToken(tokens: Record<string, unknown>, accessToken: string): string {
  const refreshToken = String(tokens.refresh_token || '')
  return refreshToken || accessToken
}

function tokensExpiresAt(tokens: Record<string, unknown>, fallbackMs: number | null): string | null {
  if (tokens.expires_in) return new Date(Date.now() + Number(tokens.expires_in) * 1000).toISOString()
  return fallbackMs === null ? null : new Date(Date.now() + fallbackMs).toISOString()
}

async function storedOrFetchedUsername(tokens: Record<string, unknown>, fetchFn: (accessToken: string) => Promise<string | null>, fallback: string): Promise<string> {
  const stored = String(tokens.username || '').trim()
  if (stored) return stored
  return (await fetchFn(String(tokens.access_token || ''))) || fallback
}

function youtubeAccountId(tokens: Record<string, unknown>, userId: string): string {
  return String(tokens.id || tokens.user_id || userId)
}

async function saveYoutubeTokens(userId: string, tokens: Record<string, unknown>): Promise<void> {
  const accessToken = String(tokens.access_token || '')
  if (!accessToken) throw new Error('tokens sin access_token')
  const refreshToken = youtubeRefreshToken(tokens, accessToken)
  const expiresAt = tokensExpiresAt(tokens, null)
  const username = await storedOrFetchedUsername(tokens, fetchYoutubeUsername, '')
  const accountId = youtubeAccountId(tokens, userId)

  await pool.query(
    `INSERT INTO social_accounts (user_id, platform, platform_account_id, platform_username, access_token, refresh_token, token_expires_at)
     VALUES ($1, 'youtube', $2, $3, $4, $5, $6)
     ON CONFLICT (user_id, platform) DO UPDATE SET
       access_token = EXCLUDED.access_token,
       refresh_token = EXCLUDED.refresh_token,
       token_expires_at = EXCLUDED.token_expires_at,
       platform_username = CASE WHEN EXCLUDED.platform_username <> '' THEN EXCLUDED.platform_username ELSE social_accounts.platform_username END,
       platform_account_id = EXCLUDED.platform_account_id,
       updated_at = NOW()`,
    [userId, accountId, username, accessToken, refreshToken, expiresAt]
  )
}

// ============================================================================
// Instagram (Meta)
// ============================================================================

async function requireInstagramShortToken(shortData: Record<string, unknown>): Promise<string> {
  const shortToken = String(shortData.access_token || '')
  if (!shortToken) throw new Error(`Respuesta sin access_token short-lived`)
  return shortToken
}

async function fetchLongLivedInstagramToken(clientId: string, clientSecret: string, shortToken: string): Promise<Record<string, unknown> | null> {
  try {
    const longParams = new URLSearchParams({
      grant_type: 'fb_exchange_token',
      client_id: clientId,
      client_secret: clientSecret,
      fb_exchange_token: shortToken,
    })
    const longResp = await fetch(`https://graph.facebook.com/oauth/access_token?${longParams.toString()}`)
    if (longResp.ok) {
      const longData = (await longResp.json()) as Record<string, unknown>
      if (longData.access_token) return longData
    }
  } catch {
    /* mantener short */
  }
  return null
}

async function exchangeInstagramTokens(code: string): Promise<Record<string, unknown>> {
  const { clientId, clientSecret, redirectUri } = getInstagramConfig()
  const shortParams = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    redirect_uri: redirectUri,
    code,
  })
  const shortResp = await fetch(`https://graph.facebook.com/v18.0/oauth/access_token?${shortParams.toString()}`)
  if (!shortResp.ok) throw new Error(`Meta short token HTTP ${shortResp.status}`)
  const shortData = (await shortResp.json()) as Record<string, unknown>
  const shortToken = await requireInstagramShortToken(shortData)
  const longData = await fetchLongLivedInstagramToken(clientId, clientSecret, shortToken)
  const tokens = longData ?? shortData
  await applyOptionalUsername(tokens, fetchInstagramUsername)
  return tokens
}

function igAccountName(ig: Record<string, unknown>): string | null {
  const uname = String(ig.username || '').trim()
  if (uname) return uname
  const name = String(ig.name || '').trim()
  return name || null
}

function instagramPageUsername(data: Record<string, unknown>): string | null {
  const pages = (data.data as Array<Record<string, unknown>>) || []
  for (const page of pages) {
    const ig = page.instagram_business_account as Record<string, unknown> | undefined
    if (ig) {
      const name = igAccountName(ig)
      if (name) return name
    }
  }
  return null
}

async function fetchInstagramBusinessName(accessToken: string): Promise<string | null> {
  const accUrl = `https://graph.facebook.com/v18.0/me/accounts?fields=id,name,instagram_business_account{id,username,name}&access_token=${accessToken}`
  const resp = await fetch(accUrl)
  if (resp.status === 200) {
    return instagramPageUsername((await resp.json()) as Record<string, unknown>)
  }
  return null
}

async function fetchInstagramMeName(accessToken: string): Promise<string | null> {
  const meResp = await fetch(`https://graph.facebook.com/v18.0/me?fields=id,name&access_token=${accessToken}`)
  if (meResp.status === 200) {
    const me = (await meResp.json()) as Record<string, unknown>
    const name = String(me.name || '').trim()
    if (name) return name
  }
  return null
}

async function instagramUsernameOrNull(accessToken: string): Promise<string | null> {
  const pageName = await fetchInstagramBusinessName(accessToken)
  if (pageName) return pageName
  return fetchInstagramMeName(accessToken)
}

async function fetchInstagramUsername(accessToken: string): Promise<string | null> {
  if (!accessToken) return null
  try {
    const name = await instagramUsernameOrNull(accessToken)
    if (name) return name
  } catch {
    /* opcional */
  }
  return 'Instagram User'
}

function instagramAccountId(tokens: Record<string, unknown>, userId: string): string {
  return String(tokens.user_id || tokens.id || userId)
}

async function saveInstagramTokens(userId: string, tokens: Record<string, unknown>): Promise<void> {
  const accessToken = String(tokens.access_token || '')
  if (!accessToken) throw new Error('tokens sin access_token')
  const refreshToken = accessToken
  const username = await storedOrFetchedUsername(tokens, fetchInstagramUsername, 'Instagram User')
  const accountId = instagramAccountId(tokens, userId)
  const expiresAt = tokensExpiresAt(tokens, 60 * 24 * 3600 * 1000)

  await pool.query(
    `INSERT INTO social_accounts (user_id, platform, platform_account_id, platform_username, access_token, refresh_token, token_expires_at)
     VALUES ($1, 'instagram', $2, $3, $4, $5, $6)
     ON CONFLICT (user_id, platform) DO UPDATE SET
       access_token = EXCLUDED.access_token,
       refresh_token = EXCLUDED.refresh_token,
       token_expires_at = EXCLUDED.token_expires_at,
       platform_username = EXCLUDED.platform_username,
       platform_account_id = EXCLUDED.platform_account_id,
       updated_at = NOW()`,
    [userId, accountId, username, accessToken, refreshToken, expiresAt]
  )
}

// ============================================================================
// TikTok
// ============================================================================

async function exchangeTiktokCode(code: string, codeVerifier: string): Promise<Record<string, unknown>> {
  const { clientKey, clientSecret, redirectUri } = getTiktokConfig()
  const body = new URLSearchParams({
    client_key: clientKey,
    client_secret: clientSecret,
    code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri,
    code_verifier: codeVerifier,
  })
  const resp = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!resp.ok) throw new Error(`TikTok token HTTP ${resp.status}: ${(await resp.text()).slice(0, 200)}`)
  const tokens = (await resp.json()) as Record<string, unknown>
  try {
    const username = await fetchTiktokUsername(String(tokens.access_token || ''))
    if (username) tokens.username = username
  } catch {
    /* opcional */
  }
  return tokens
}

function tiktokUserDisplayName(data: Record<string, unknown>): string | null {
  const user = (data.data as Record<string, unknown>)?.user as Record<string, unknown> | undefined
  const name = String(user?.display_name || user?.username || '').trim()
  return name || null
}

async function fetchTiktokUsername(accessToken: string): Promise<string | null> {
  if (!accessToken) return null
  try {
    const resp = await fetch('https://open.tiktokapis.com/v2/user/info/?fields=display_name,username', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (resp.status === 200) {
      return tiktokUserDisplayName((await resp.json()) as Record<string, unknown>)
    }
  } catch {
    /* opcional */
  }
  return null
}

function tiktokAccountId(tokens: Record<string, unknown>, userId: string): string {
  return String(tokens.open_id || tokens.user_id || userId)
}

async function saveTiktokTokens(userId: string, tokens: Record<string, unknown>): Promise<void> {
  const accessToken = String(tokens.access_token || '')
  if (!accessToken) throw new Error('tokens sin access_token')
  const refreshToken = String(tokens.refresh_token || '')
  const username = await storedOrFetchedUsername(tokens, fetchTiktokUsername, 'TikTok User')
  const accountId = tiktokAccountId(tokens, userId)
  const expiresAt = tokensExpiresAt(tokens, null)

  await pool.query(
    `INSERT INTO social_accounts (user_id, platform, platform_account_id, platform_username, access_token, refresh_token, token_expires_at)
     VALUES ($1, 'tiktok', $2, $3, $4, $5, $6)
     ON CONFLICT (user_id, platform) DO UPDATE SET
       access_token = EXCLUDED.access_token,
       refresh_token = EXCLUDED.refresh_token,
       token_expires_at = EXCLUDED.token_expires_at,
       platform_username = EXCLUDED.platform_username,
       platform_account_id = EXCLUDED.platform_account_id,
       updated_at = NOW()`,
    [userId, accountId, username, accessToken, refreshToken, expiresAt]
  )
}

// ============================================================================
// Connect endpoints
// ============================================================================

socialAuthRouter.get('/youtube/connect', authMiddleware, (req: AuthRequest, res: Response) => {
  const { clientId, redirectUri } = getGoogleConfig()
  if (!clientId) {
    return res.status(500).json({ detail: 'GOOGLE_CLIENT_ID no está configurado en el archivo .env del backend' })
  }
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube.upload',
    access_type: 'offline',
    prompt: 'consent',
    state: encodeStateUserId(req.user!.id),
  })
  return res.json({ auth_url: `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}` })
})

socialAuthRouter.get('/instagram/connect', authMiddleware, (req: AuthRequest, res: Response) => {
  const { clientId, redirectUri } = getInstagramConfig()
  if (!clientId) {
    return res.status(500).json({
      detail: 'INSTAGRAM_CLIENT_ID / META_APP_ID no está configurado en el archivo .env del backend',
    })
  }
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: 'instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management',
    response_type: 'code',
    state: encodeStateUserId(req.user!.id),
    auth_type: 'rerequest',
  })
  const url = `https://www.facebook.com/v18.0/dialog/oauth?${params.toString()}`
  return res.json({ auth_url: url, url })
})

socialAuthRouter.get('/tiktok/connect', authMiddleware, (req: AuthRequest, res: Response) => {
  const { clientKey, redirectUri } = getTiktokConfig()
  if (!clientKey) {
    return res.status(500).json({ detail: 'TIKTOK_CLIENT_KEY no está configurado en el archivo .env del backend' })
  }
  const { verifier, challenge } = generatePkcePair()
  const state = encodeState({ user_id: String(req.user!.id), code_verifier: verifier })
  const params = new URLSearchParams({
    client_key: clientKey,
    response_type: 'code',
    scope: 'user.info.basic,video.upload,video.publish',
    redirect_uri: redirectUri,
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
  })
  const url = `https://www.tiktok.com/v2/auth/authorize/?${params.toString()}`
  return res.json({ auth_url: url, url })
})

// ============================================================================
// Callback endpoints (públicos, sin auth)
// ============================================================================

type CallbackOutcome = { status: 'error'; extra: string } | { status: 'success' }

function callbackErrorDetail(exc: unknown): string {
  return String((exc as { message?: string })?.message || exc).slice(0, 200)
}

async function youtubeCallbackOutcome(code: string, state: string | undefined): Promise<CallbackOutcome> {
  let tokens: Record<string, unknown>
  try {
    tokens = await exchangeGoogleTokens(code)
  } catch (exc: any) {
    return { status: 'error', extra: callbackErrorDetail(exc) }
  }
  const userId = decodeState(state)?.user_id as string | undefined
  if (!userId) return { status: 'error', extra: 'invalid_state' }
  try {
    await saveYoutubeTokens(String(userId), tokens)
  } catch (exc: any) {
    return { status: 'error', extra: callbackErrorDetail(exc) }
  }
  return { status: 'success' }
}

socialAuthRouter.get('/youtube/callback', async (req: Request, res: Response) => {
  const frontendBase = getFrontendBase()
  const { code, state, error } = req.query as Record<string, string | undefined>
  if (error) return redirectWithIntegration(res, frontendBase, 'youtube', 'error', error)
  if (!code) return redirectWithIntegration(res, frontendBase, 'youtube', 'error', 'missing_code')
  const outcome = await youtubeCallbackOutcome(code, state)
  if (outcome.status === 'error') return redirectWithIntegration(res, frontendBase, 'youtube', 'error', outcome.extra)
  return redirectWithIntegration(res, frontendBase, 'youtube', 'success')
})

async function instagramCallbackOutcome(code: string, state: string | undefined): Promise<CallbackOutcome> {
  try {
    const tokens = await exchangeInstagramTokens(code)
    const userId = decodeState(state)?.user_id as string | undefined
    if (!userId) throw new Error('invalid_state')
    await saveInstagramTokens(String(userId), tokens)
    return { status: 'success' }
  } catch (exc: any) {
    console.error('[instagram/callback] error:', exc?.message || exc)
    return { status: 'error', extra: 'Error al guardar token' }
  }
}

socialAuthRouter.get('/instagram/callback', async (req: Request, res: Response) => {
  const frontendBase = getFrontendBase()
  const { code, state, error } = req.query as Record<string, string | undefined>
  if (error) return redirectWithIntegration(res, frontendBase, 'instagram', 'error', error)
  if (!code) return redirectWithIntegration(res, frontendBase, 'instagram', 'error', 'missing_code')
  const outcome = await instagramCallbackOutcome(code, state)
  if (outcome.status === 'error') return redirectWithIntegration(res, frontendBase, 'instagram', 'error', outcome.extra)
  return redirectWithIntegration(res, frontendBase, 'instagram', 'success')
})

async function tiktokCallbackOutcome(code: string, state: string | undefined): Promise<CallbackOutcome> {
  try {
    const data = decodeState(state)
    const userId = data?.user_id as string | undefined
    const codeVerifier = data?.code_verifier as string | undefined
    if (!userId) throw new Error('invalid_state')
    if (!codeVerifier) throw new Error('missing_code_verifier')
    const tokens = await exchangeTiktokCode(code, codeVerifier)
    await saveTiktokTokens(String(userId), tokens)
    return { status: 'success' }
  } catch (exc: any) {
    console.error('[tiktok/callback] error:', exc?.message || exc)
    return { status: 'error', extra: 'Error al guardar token' }
  }
}

socialAuthRouter.get('/tiktok/callback', async (req: Request, res: Response) => {
  const frontendBase = getFrontendBase()
  const { code, state, error } = req.query as Record<string, string | undefined>
  if (error) return redirectWithIntegration(res, frontendBase, 'tiktok', 'error', error)
  if (!code) return redirectWithIntegration(res, frontendBase, 'tiktok', 'error', 'missing_code')
  const outcome = await tiktokCallbackOutcome(code, state)
  if (outcome.status === 'error') return redirectWithIntegration(res, frontendBase, 'tiktok', 'error', outcome.extra)
  return redirectWithIntegration(res, frontendBase, 'tiktok', 'success')
})
