import { Router } from 'express'
import bcrypt from 'bcryptjs'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const usersRouter = Router()

void pool.query(`ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)`).catch(() => {})
void pool.query(`ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS theme_preference VARCHAR(20) DEFAULT 'dark'`).catch(() => {})

function truncate72(pwd: string): string {
  return Buffer.from(pwd, 'utf-8').subarray(0, 72).toString('utf-8')
}

function isValidTheme(v: string): boolean {
  return v === 'dark' || v === 'light' || v === 'system'
}
function isValidAvatarUrl(v: string): boolean {
  return v.startsWith('http://') || v.startsWith('https://')
}

function toStrOrNull(v: unknown): string | null {
  return (v as string | null) ?? null
}

function nameOrNull(u: Record<string, unknown>): string | null {
  return (u.full_name as string | null) ?? null
}

function themeOrDefault(v: unknown): string {
  return (v as string) ?? 'dark'
}

function profileResponse(u: Record<string, unknown>, avatarUrl: string | null, theme: string): Record<string, unknown> {
  return {
    id: u.id,
    email: u.email,
    full_name: nameOrNull(u),
    name: nameOrNull(u),
    avatar_url: avatarUrl,
    theme_preference: theme,
    created_at: new Date(u.created_at as string).toISOString(),
  }
}

function userRowResponse(u: Record<string, unknown>): Record<string, unknown> {
  return profileResponse(u, (u.avatar_url as string | null) ?? null, themeOrDefault(u.theme_preference))
}

async function fallbackProfileResponse(userId: string): Promise<Record<string, unknown> | null> {
  const fallback = await pool.query('SELECT id, email, full_name, created_at FROM usuarios WHERE id = $1', [userId])
  if (fallback.rows.length === 0) return null
  return profileResponse(fallback.rows[0] as Record<string, unknown>, null, 'dark')
}

async function handleGetMe(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  try {
    const r = await pool.query('SELECT id, email, full_name, avatar_url, theme_preference, created_at FROM usuarios WHERE id = $1', [userId])
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    const u = r.rows[0] as Record<string, unknown>
    return res.json(profileResponse(u, toStrOrNull(u.avatar_url), themeOrDefault(u.theme_preference)))
  } catch (err) {
    console.error('GET /users/me error', err)
    try {
      const fallback = await fallbackProfileResponse(userId)
      if (fallback) return res.json(fallback)
    } catch {}
    return res.status(500).json({ detail: 'Error interno' })
  }
}

// Paridad con FastAPI (users.py): rutas canónicas `/users/me*` + alias `/me*`.
// El router se monta con prefijos '' y '/api' (igual que `include_router`).
usersRouter.get('/users/me', authMiddleware, handleGetMe)
usersRouter.get('/me', authMiddleware, handleGetMe)

// ----------------------------------------------------------------------------
// PUT /users/me — actualización de perfil
// ----------------------------------------------------------------------------

interface UpdateContext {
  updates: string[]
  values: unknown[]
}

interface ProfileFlags {
  hasFullName: boolean
  hasEmail: boolean
  hasAvatar: boolean
  hasTheme: boolean
}

type FieldResult = { error?: string; sql?: string; value?: unknown }

type ProfileUpdate = UpdateContext | { status: number; detail: string }

function hasField(body: Record<string, unknown>, keys: string[]): boolean {
  return keys.some((k) => Object.prototype.hasOwnProperty.call(body, k))
}

function profileFlags(body: Record<string, unknown>): ProfileFlags {
  return {
    hasFullName: hasField(body, ['full_name', 'nombre']),
    hasEmail: hasField(body, ['email']),
    hasAvatar: hasField(body, ['avatar_url']),
    hasTheme: hasField(body, ['theme_preference']),
  }
}

function nothingToUpdate(flags: ProfileFlags): boolean {
  return !flags.hasFullName && !flags.hasEmail && !flags.hasAvatar && !flags.hasTheme
}

function overLengthName(v: unknown): boolean {
  return typeof v === 'string' && v.length > 100
}

function fullNameField(raw: unknown, idx: number): FieldResult {
  const v = raw ?? null
  if (v !== null && overLengthName(v)) return { error: 'full_name debe tener máximo 100 caracteres' }
  return { sql: `full_name = $${idx}`, value: v }
}

function invalidEmailFormat(v: unknown): boolean {
  return typeof v !== 'string' || !v.includes('@')
}

async function emailFieldError(v: unknown, userId: string): Promise<string | null> {
  if (v === null) return null
  if (invalidEmailFormat(v)) return 'email inválido'
  const exists = await pool.query('SELECT id FROM usuarios WHERE email = $1 AND id <> $2', [v, userId])
  if (exists.rows.length > 0) return 'El email ya está registrado'
  return null
}

async function emailField(raw: unknown, idx: number, userId: string): Promise<FieldResult> {
  const v = raw ?? null
  const error = await emailFieldError(v, userId)
  if (error) return { error }
  return { sql: `email = $${idx}`, value: v }
}

function normalizedAvatar(raw: unknown): string | null {
  let normalized = (raw as string | null) ?? null
  if (normalized !== null && normalized.trim() === '') normalized = null
  return normalized
}

function avatarFieldError(normalized: string | null): string | null {
  if (normalized === null) return null
  if (normalized.length > 500) return 'avatar_url debe tener máximo 500 caracteres'
  if (!isValidAvatarUrl(normalized)) return 'avatar_url debe ser una URL http(s)'
  return null
}

function avatarField(raw: unknown, idx: number): FieldResult {
  const normalized = normalizedAvatar(raw)
  const error = avatarFieldError(normalized)
  if (error) return { error }
  return { sql: `avatar_url = $${idx}`, value: normalized }
}

function invalidThemeValue(v: unknown): boolean {
  return v !== null && !isValidTheme(v as string)
}

function themeField(raw: unknown, idx: number): FieldResult {
  const v = raw ?? null
  if (invalidThemeValue(v)) return { error: "theme_preference debe ser 'dark', 'light' o 'system'" }
  if (v === null) return {}
  return { sql: `theme_preference = $${idx}`, value: v }
}

async function applyOptionalField(ctx: UpdateContext, enabled: boolean, compute: () => FieldResult | Promise<FieldResult>): Promise<string | null> {
  if (!enabled) return null
  const result = await compute()
  if (result.error) return result.error
  if (result.sql) {
    ctx.updates.push(result.sql)
    ctx.values.push(result.value)
  }
  return null
}

async function applyBasicFields(body: Record<string, unknown>, ctx: UpdateContext, userId: string, flags: ProfileFlags): Promise<string | null> {
  const nameError = await applyOptionalField(ctx, flags.hasFullName, () => fullNameField(body.full_name ?? body.nombre, ctx.updates.length + 1))
  if (nameError) return nameError
  const emailError = await applyOptionalField(ctx, flags.hasEmail, () => emailField(body.email, ctx.updates.length + 1, userId))
  if (emailError) return emailError
  return null
}

async function applyMediaFields(body: Record<string, unknown>, ctx: UpdateContext, flags: ProfileFlags): Promise<string | null> {
  const avatarError = await applyOptionalField(ctx, flags.hasAvatar, () => avatarField(body.avatar_url, ctx.updates.length + 1))
  if (avatarError) return avatarError
  const themeError = await applyOptionalField(ctx, flags.hasTheme, () => themeField(body.theme_preference, ctx.updates.length + 1))
  if (themeError) return themeError
  return null
}

async function buildProfileUpdates(body: Record<string, unknown>, userId: string): Promise<ProfileUpdate> {
  const flags = profileFlags(body)
  if (nothingToUpdate(flags)) return { status: 400, detail: 'Nada para actualizar' }
  const ctx: UpdateContext = { updates: [], values: [] }
  const basicError = await applyBasicFields(body, ctx, userId, flags)
  if (basicError) return { status: 422, detail: basicError }
  const mediaError = await applyMediaFields(body, ctx, flags)
  if (mediaError) return { status: 422, detail: mediaError }
  if (ctx.updates.length === 0) return { status: 400, detail: 'Nada para actualizar' }
  return ctx
}

function profileUpdateQuery(updates: string[]): string {
  return `UPDATE usuarios SET ${updates.join(', ')} WHERE id = $${updates.length + 1} RETURNING id, email, full_name, avatar_url, theme_preference, created_at`
}

function coreProfileFields(updates: string[]): string[] {
  return updates.filter((u) => !u.includes('avatar_url') && !u.includes('theme_preference'))
}

function fallbackUpdateQuery(updates: string[]): string {
  return `UPDATE usuarios SET ${coreProfileFields(updates).join(', ')} WHERE id = $${updates.length + 1} RETURNING id, email, full_name, created_at`
}

async function retryCoreProfileUpdate(ctx: UpdateContext, e: unknown, res: import('express').Response): Promise<import('express').Response> {
  const fallbackQ = fallbackUpdateQuery(ctx.updates)
  if (fallbackQ.includes('SET  WHERE')) throw e
  const r2 = await pool.query(fallbackQ, ctx.values.slice(0, -1).concat(ctx.values[ctx.values.length - 1]))
  if (r2.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
  return res.json(profileResponse(r2.rows[0] as Record<string, unknown>, null, 'dark'))
}

async function executeProfileUpdate(ctx: UpdateContext, userId: string, res: import('express').Response): Promise<import('express').Response> {
  ctx.values.push(userId)
  const q = profileUpdateQuery(ctx.updates)
  try {
    const r = await pool.query(q, ctx.values)
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    return res.json(userRowResponse(r.rows[0] as Record<string, unknown>))
  } catch (e) {
    return await retryCoreProfileUpdate(ctx, e, res)
  }
}

function buildUpdateHandler() {
  return async (req: AuthRequest, res: import('express').Response) => {
    const userId = req.user!.id
    const body = req.body as Record<string, unknown>
    const built = await buildProfileUpdates(body, userId)
    if ('status' in built) return res.status(built.status).json({ detail: built.detail })
    try {
      return await executeProfileUpdate(built, userId, res)
    } catch (err) {
      console.error('PUT /users/me error', err)
      return res.status(500).json({ detail: 'Error interno' })
    }
  }
}

// PUT `/users/me` (canónica) + alias `/me`; PATCH solo sobre `/me` (paridad FastAPI).
const updateHandler = buildUpdateHandler()
usersRouter.put('/users/me', authMiddleware, updateHandler)
usersRouter.put('/me', authMiddleware, updateHandler)
usersRouter.patch('/me', authMiddleware, updateHandler)

// ----------------------------------------------------------------------------
// Contraseñas
// ----------------------------------------------------------------------------

function missingString(v: unknown): boolean {
  return !v || typeof v !== 'string'
}

function passwordRequestError(current: unknown, next: unknown): { status: number; detail: string } | null {
  if (missingString(current)) return { status: 422, detail: 'current_password es requerido' }
  if (missingString(next)) return { status: 422, detail: 'new_password es requerido' }
  return null
}

function newPasswordConstraintError(new_password: string): string | null {
  if (new_password.length < 8 || new_password.length > 128) return 'new_password debe tener entre 8 y 128 caracteres'
  return null
}

function passwordPolicyError(current: unknown, next: string): { status: number; detail: string } | null {
  const lengthError = newPasswordConstraintError(next)
  if (lengthError) return { status: 422, detail: lengthError }
  if (current === next) return { status: 400, detail: 'La nueva contraseña debe ser diferente' }
  return null
}

async function wrongCurrentPassword(userId: string, current_password: string): Promise<{ status: number; detail: string } | null> {
  const r = await pool.query('SELECT hashed_password FROM usuarios WHERE id = $1', [userId])
  if (r.rows.length === 0) return { status: 401, detail: 'Usuario no encontrado' }
  const hashed: string = r.rows[0].hashed_password as string
  const ok = await bcrypt.compare(truncate72(current_password), hashed)
  if (!ok) return { status: 400, detail: 'La contraseña actual es incorrecta' }
  return null
}

async function changePasswordRow(userId: string, current_password: string, new_password: string): Promise<{ status: number; detail: string } | null> {
  const wrong = await wrongCurrentPassword(userId, current_password)
  if (wrong) return wrong
  const newHash = await bcrypt.hash(truncate72(new_password), 10)
  await pool.query('UPDATE usuarios SET hashed_password = $1 WHERE id = $2', [newHash, userId])
  return null
}

async function handleChangePassword(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const { current_password, new_password } = req.body as { current_password?: string; new_password?: string }
  const requestError = passwordRequestError(current_password, new_password)
  if (requestError) return res.status(requestError.status).json({ detail: requestError.detail })
  const policyError = passwordPolicyError(current_password, new_password as string)
  if (policyError) return res.status(policyError.status).json({ detail: policyError.detail })
  try {
    const failure = await changePasswordRow(userId, current_password as string, new_password as string)
    if (failure) return res.status(failure.status).json({ detail: failure.detail })
    return res.json({ detail: 'Contraseña actualizada correctamente' })
  } catch (err) {
    console.error('POST /users/me/change-password error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
}

usersRouter.post('/users/me/change-password', authMiddleware, handleChangePassword)
usersRouter.post('/me/change-password', authMiddleware, handleChangePassword)
usersRouter.put('/me/password', authMiddleware, handleChangePassword)
