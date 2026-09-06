import { Router } from 'express'
import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const authRouter = Router()

function getSecret(): string {
  return process.env.JWT_SECRET ?? 'dev_secret_key_clipsai_2026_super_secure_local'
}
function getAlgorithm(): jwt.Algorithm {
  return (process.env.JWT_ALGORITHM as jwt.Algorithm) ?? 'HS256'
}
function getExpireMinutes(): number {
  return parseInt(process.env.JWT_EXPIRE_MINUTES ?? '60', 10) || 60
}
function truncate72(pwd: string): string {
  return Buffer.from(pwd, 'utf-8').subarray(0, 72).toString('utf-8')
}
function createAccessToken(sub: string): string {
  const now = Math.floor(Date.now() / 1000)
  const exp = now + getExpireMinutes() * 60
  return jwt.sign({ sub, iat: now, exp, type: 'access' }, getSecret(), { algorithm: getAlgorithm() })
}
function isValidEmail(email: string): boolean {
  return typeof email === 'string' && email.includes('@') && email.length <= 255
}

authRouter.post('/registro', async (req, res) => {
  const { email, password, full_name, fullName } = req.body as Record<string, unknown>
  const emailStr = typeof email === 'string' ? email.trim() : ''
  const pwdStr = typeof password === 'string' ? password : ''
  const nameStr = (typeof full_name === 'string' ? full_name : typeof fullName === 'string' ? fullName : null) as string | null

  if (!isValidEmail(emailStr)) return res.status(422).json({ detail: 'email inválido' })
  if (typeof pwdStr !== 'string' || pwdStr.length < 8 || pwdStr.length > 128) return res.status(422).json({ detail: 'password debe tener entre 8 y 128 caracteres' })
  if (nameStr !== null && typeof nameStr === 'string' && nameStr.length > 100) return res.status(422).json({ detail: 'full_name debe tener máximo 100 caracteres' })

  try {
    const exists = await pool.query('SELECT id FROM usuarios WHERE email = $1', [emailStr])
    if (exists.rows.length > 0) return res.status(409).json({ detail: 'El email ya está registrado' })

    const hashed = await bcrypt.hash(truncate72(pwdStr), 10)
    const r = await pool.query(
      'INSERT INTO usuarios (email, hashed_password, full_name) VALUES ($1,$2,$3) RETURNING id, email, full_name, created_at, updated_at',
      [emailStr, hashed, nameStr ?? null]
    )
    const u = r.rows[0] as Record<string, unknown>
    return res.status(201).json({ id: u.id, email: u.email, full_name: u.full_name ?? null, created_at: new Date(u.created_at as string).toISOString(), updated_at: new Date((u.updated_at as string) ?? (u.created_at as string)).toISOString() })
  } catch (err: unknown) {
    const e = err as { code?: string }
    if (e?.code === '23505') return res.status(409).json({ detail: 'El email ya está registrado' })
    console.error('POST /auth/registro error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})

async function handleLogin(emailRaw: unknown, pwdRaw: unknown, res: import('express').Response) {
  const email = typeof emailRaw === 'string' ? emailRaw.trim() : ''
  const password = typeof pwdRaw === 'string' ? pwdRaw : ''
  if (!email || !password) return res.status(401).json({ detail: 'Credenciales inválidas' })
  try {
    const r = await pool.query('SELECT id, hashed_password FROM usuarios WHERE email = $1', [email])
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Credenciales inválidas' })
    const row = r.rows[0] as Record<string, unknown>
    const ok = await bcrypt.compare(truncate72(password), row.hashed_password as string)
    if (!ok) return res.status(401).json({ detail: 'Credenciales inválidas' })
    const token = createAccessToken(String(row.id))
    return res.json({ access_token: token, token_type: 'bearer' })
  } catch (err) {
    console.error('POST /auth/login error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
}

authRouter.post('/login', async (req, res) => {
  const { email, password } = req.body as Record<string, unknown>
  return handleLogin(email, password, res)
})

authRouter.post('/login/form', async (req, res) => {
  const username = (req.body as Record<string, unknown>).username as string | undefined
  const password = (req.body as Record<string, unknown>).password as string | undefined
  return handleLogin(username, password, res)
})

authRouter.get('/me', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  try {
    const r = await pool.query('SELECT id, email, full_name, created_at, updated_at FROM usuarios WHERE id = $1', [userId])
    if (r.rows.length === 0) return res.status(401).json({ detail: 'Usuario no encontrado' })
    const u = r.rows[0] as Record<string, unknown>
    return res.json({ id: u.id, email: u.email, full_name: u.full_name ?? null, created_at: new Date(u.created_at as string).toISOString(), updated_at: new Date((u.updated_at as string) ?? (u.created_at as string)).toISOString() })
  } catch (err) {
    console.error('GET /auth/me error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})
