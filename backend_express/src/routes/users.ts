import { Router } from 'express'
import bcrypt from 'bcrypt'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const usersRouter = Router()

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
    const r = await pool.query(
      'SELECT id, email, full_name, avatar_url, theme_preference, created_at FROM usuarios WHERE id = $1',
      [userId]
    )
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    const u = r.rows[0] as Record<string, unknown>
    return res.json({
      id: u.id,
      email: u.email,
      full_name: u.full_name ?? null,
      avatar_url: u.avatar_url ?? null,
      theme_preference: (u.theme_preference as string) ?? 'dark',
      created_at: new Date(u.created_at as string).toISOString(),
    })
  } catch (err) {
    console.error('GET /users/me error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})

usersRouter.patch('/me', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const { full_name, avatar_url, theme_preference } = req.body as {
    full_name?: string | null
    avatar_url?: string | null
    theme_preference?: string | null
  }

  const updates: string[] = []
  const values: unknown[] = []
  let idx = 1

  if (full_name !== undefined) {
    if (full_name !== null && full_name.length > 100) {
      return res.status(422).json({ detail: 'full_name debe tener máximo 100 caracteres' })
    }
    updates.push(`full_name = $${idx++}`)
    values.push(full_name ?? null)
  }

  if (avatar_url !== undefined) {
    let normalized: string | null = avatar_url ?? null
    if (normalized !== null && normalized.trim() === '') normalized = null
    if (normalized !== null) {
      if (normalized.length > 500) return res.status(422).json({ detail: 'avatar_url debe tener máximo 500 caracteres' })
      if (!isValidAvatarUrl(normalized)) return res.status(422).json({ detail: 'avatar_url debe ser una URL http(s)' })
    }
    updates.push(`avatar_url = $${idx++}`)
    values.push(normalized)
  }

  if (theme_preference !== undefined) {
    if (theme_preference !== null && !isValidTheme(theme_preference)) {
      return res.status(422).json({ detail: "theme_preference debe ser 'dark', 'light' o 'system'" })
    }
    if (theme_preference !== null) {
      updates.push(`theme_preference = $${idx++}`)
      values.push(theme_preference)
    }
  }

  if (updates.length === 0) {
    return res.status(400).json({ detail: 'Nada para actualizar' })
  }

  try {
    values.push(userId)
    const q = `UPDATE usuarios SET ${updates.join(', ')} WHERE id = $${idx} RETURNING id, email, full_name, avatar_url, theme_preference, created_at`
    const r = await pool.query(q, values)
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    const u = r.rows[0] as Record<string, unknown>
    return res.json({
      id: u.id,
      email: u.email,
      full_name: u.full_name ?? null,
      avatar_url: u.avatar_url ?? null,
      theme_preference: (u.theme_preference as string) ?? 'dark',
      created_at: new Date(u.created_at as string).toISOString(),
    })
  } catch (err) {
    console.error('PATCH /users/me error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})

usersRouter.put('/me/password', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const { current_password, new_password } = req.body as { current_password?: string; new_password?: string }

  if (!current_password || typeof current_password !== 'string') {
    return res.status(422).json({ detail: 'current_password es requerido' })
  }
  if (!new_password || typeof new_password !== 'string') {
    return res.status(422).json({ detail: 'new_password es requerido' })
  }
  if (new_password.length < 8 || new_password.length > 128) {
    return res.status(422).json({ detail: 'new_password debe tener entre 8 y 128 caracteres' })
  }
  if (current_password === new_password) {
    return res.status(400).json({ detail: 'La nueva contraseña debe ser diferente' })
  }

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
    console.error('PUT /users/me/password error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})
