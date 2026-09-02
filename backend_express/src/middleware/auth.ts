import type { Request, Response, NextFunction } from 'express'
import jwt from 'jsonwebtoken'

export interface AuthUser {
  id: string
}

export interface AuthRequest extends Request {
  user?: AuthUser
}

function getSecret(): string {
  return process.env.JWT_SECRET ?? 'changeme'
}

function getAlgorithm(): jwt.Algorithm {
  return (process.env.JWT_ALGORITHM as jwt.Algorithm) ?? 'HS256'
}

export function authMiddleware(req: AuthRequest, res: Response, next: NextFunction) {
  const header = req.headers.authorization
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ detail: 'Not authenticated' })
  }
  const token = header.slice(7)
  try {
    const payload = jwt.verify(token, getSecret(), { algorithms: [getAlgorithm()] }) as { sub: string }
    if (!payload.sub) throw new Error('no sub')
    req.user = { id: payload.sub }
    next()
  } catch (err: unknown) {
    if (err instanceof jwt.TokenExpiredError) {
      return res.status(401).json({ detail: 'Token expirado' })
    }
    return res.status(401).json({ detail: 'Token invalido' })
  }
}
