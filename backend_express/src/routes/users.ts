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

usersRouter.get('/me', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  try {
    const r = await pool.query('SELECT id, email, full_name, avatar_url, theme_preference, created_at FROM usuarios WHERE id = $1', [userId])
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    const u = r.rows[0] as Record<string, unknown>
    return res.json({ id: u.id, email: u.email, full_name: u.full_name ?? null, name: u.full_name ?? null, avatar_url: u.avatar_url ?? null, theme_preference: (u.theme_preference as string) ?? 'dark', created_at: new Date(u.created_at as string).toISOString() })
  } catch (err) {
    console.error('GET /users/me error', err)
    try {
      const fallback = await pool.query('SELECT id, email, full_name, created_at FROM usuarios WHERE id = $1', [userId])
      if (fallback.rows.length > 0) {
        const u = fallback.rows[0] as Record<string, unknown>
        return res.json({ id: u.id, email: u.email, full_name: u.full_name ?? null, name: u.full_name ?? null, avatar_url: null, theme_preference: 'dark', created_at: new Date(u.created_at as string).toISOString() })
      }
    } catch {}
    return res.status(500).json({ detail: 'Error interno' })
  }
})

function buildUpdateHandler() {
  return async (req: AuthRequest, res: import('express').Response) => {
    const userId = req.user!.id
    const body = req.body as Record<string, unknown>
    const fullNameRaw = (body.full_name ?? body.nombre) as string | null | undefined
    const emailRaw = body.email as string | null | undefined
    const avatarRaw = body.avatar_url as string | null | undefined
    const themeRaw = body.theme_preference as string | null | undefined

    const hasFullName = Object.prototype.hasOwnProperty.call(body, 'full_name') || Object.prototype.hasOwnProperty.call(body, 'nombre')
    const hasEmail = Object.prototype.hasOwnProperty.call(body, 'email')
    const hasAvatar = Object.prototype.hasOwnProperty.call(body, 'avatar_url')
    const hasTheme = Object.prototype.hasOwnProperty.call(body, 'theme_preference')

    if (!hasFullName && !hasEmail && !hasAvatar && !hasTheme) {
      return res.status(400).json({ detail: 'Nada para actualizar' })
    }

    const updates: string[] = []
    const values: unknown[] = []
    let idx = 1

    if (hasFullName) {
      const v = fullNameRaw ?? null
      if (v !== null && typeof v === 'string' && v.length > 100) return res.status(422).json({ detail: 'full_name debe tener máximo 100 caracteres' })
      updates.push(`full_name = $${idx++}`)
      values.push(v ?? null)
    }
    if (hasEmail) {
      const v = emailRaw ?? null
      if (v !== null) {
        if (typeof v !== 'string' || !v.includes('@')) return res.status(422).json({ detail: 'email inválido' })
        const exists = await pool.query('SELECT id FROM usuarios WHERE email = $1 AND id <> $2', [v, userId])
        if (exists.rows.length > 0) return res.status(409).json({ detail: 'El email ya está registrado' })
      }
      updates.push(`email = $${idx++}`)
      values.push(v)
    }
    if (hasAvatar) {
      let normalized: string | null = (avatarRaw as string | null) ?? null
      if (normalized !== null && normalized.trim() === '') normalized = null
      if (normalized !== null) {
        if (normalized.length > 500) return res.status(422).json({ detail: 'avatar_url debe tener máximo 500 caracteres' })
        if (!isValidAvatarUrl(normalized)) return res.status(422).json({ detail: 'avatar_url debe ser una URL http(s)' })
      }
      updates.push(`avatar_url = $${idx++}`)
      values.push(normalized)
    }
    if (hasTheme) {
      const v = themeRaw ?? null
      if (v !== null && !isValidTheme(v as string)) return res.status(422).json({ detail: "theme_preference debe ser 'dark', 'light' o 'system'" })
      if (v !== null) {
        updates.push(`theme_preference = $${idx++}`)
        values.push(v)
      }
    }

    if (updates.length === 0) return res.status(400).json({ detail: 'Nada para actualizar' })

    try {
      values.push(userId)
      const q = `UPDATE usuarios SET ${updates.join(', ')} WHERE id = $${idx} RETURNING id, email, full_name, avatar_url, theme_preference, created_at`
      try {
        const r = await pool.query(q, values)
        if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
        const u = r.rows[0] as Record<string, unknown>
        return res.json({ id: u.id, email: u.email, full_name: u.full_name ?? null, name: u.full_name ?? null, avatar_url: u.avatar_url ?? null, theme_preference: (u.theme_preference as string) ?? 'dark', created_at: new Date(u.created_at as string).toISOString() })
      } catch (e) {
        const fallbackQ = `UPDATE usuarios SET ${updates.filter(u => !u.includes('avatar_url') && !u.includes('theme_preference')).join(', ')} WHERE id = $${idx} RETURNING id, email, full_name, created_at`
        if (fallbackQ.includes('SET  WHERE')) throw e
        const r2 = await pool.query(fallbackQ, values.slice(0, -1).concat(values[values.length -1]))
        if (r2.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
        const u = r2.rows[0] as Record<string, unknown>
        return res.json({ id: u.id, email: u.email, full_name: u.full_name ?? null, name: u.full_name ?? null, avatar_url: null, theme_preference: 'dark', created_at: new Date(u.created_at as string).toISOString() })
      }
    } catch (err) {
      console.error('PUT /users/me error', err)
      return res.status(500).json({ detail: 'Error interno' })
    }
  }
}

usersRouter.put('/me', authMiddleware, buildUpdateHandler())
usersRouter.patch('/me', authMiddleware, buildUpdateHandler())

async function handleChangePassword(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const { current_password, new_password } = req.body as { current_password?: string; new_password?: string }
  if (!current_password || typeof current_password !== 'string') return res.status(422).json({ detail: 'current_password es requerido' })
  if (!new_password || typeof new_password !== 'string') return res.status(422).json({ detail: 'new_password es requerido' })
  if (new_password.length < 8 || new_password.length > 128) return res.status(422).json({ detail: 'new_password debe tener entre 8 y 128 caracteres' })
  if (current_password === new_password) return res.status(400).json({ detail: 'La nueva contraseña debe ser diferente' })
  try {
    const r = await pool.query('SELECT hashed_password FROM usuarios WHERE id = $1', [userId])
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    const hashed: string = r.rows[0].hashed_password as string
    const ok = await bcrypt.compare(truncate72(current_password), hashed)
    if (!ok) return res.status(400).json({ detail: 'La contraseña actual es incorrecta' })
    const newHash = await bcrypt.hash(truncate72(new_password), 10)
    await pool.query('UPDATE usuarios SET hashed_password = $1 WHERE id = $2', [newHash, userId])
    return res.json({ detail: 'Contraseña actualizada correctamente' })
  } catch (err) {
    console.error('POST /users/me/change-password error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
}

usersRouter.post('/me/change-password', authMiddleware, handleChangePassword)
usersRouter.put('/me/password', authMiddleware, handleChangePassword)
