import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const clipsRouter = Router()

const SORT_MAP: Record<string, string> = {
  created_at_desc: 'c.created_at DESC',
  created_at_asc: 'c.created_at ASC',
  score_desc: 'c.score DESC NULLS LAST, c.created_at DESC',
  score_asc: 'c.score ASC NULLS LAST, c.created_at DESC',
}

clipsRouter.get('/', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id

  const q = typeof req.query.q === 'string' ? req.query.q.trim() : undefined
  const minScoreRaw = req.query.min_score as string | undefined
  const min_score = minScoreRaw !== undefined && minScoreRaw !== '' ? Number(minScoreRaw) : undefined
  const sort_by = (typeof req.query.sort_by === 'string' ? req.query.sort_by : 'created_at_desc') as string
  const page = Math.max(1, parseInt(String(req.query.page ?? '1'), 10) || 1)
  const limit = Math.min(100, Math.max(1, parseInt(String(req.query.limit ?? '10'), 10) || 10))

  if (min_score !== undefined && (Number.isNaN(min_score) || min_score < 0 || min_score > 100)) {
    return res.status(422).json({ detail: 'min_score must be between 0 and 100' })
  }
  const orderBy = SORT_MAP[sort_by]
  if (!orderBy) {
    return res.status(422).json({ detail: 'sort_by must be one of created_at_desc, created_at_asc, score_desc, score_asc' })
  }

  const conditions: string[] = ['v.usuario_id = $1']
  const values: unknown[] = [userId]
  let paramIdx = 2

  if (q) {
    conditions.push(`(c.title ILIKE $${paramIdx} OR v.transcript ILIKE $${paramIdx})`)
    values.push(`%${q}%`)
    paramIdx += 1
  }

  if (min_score !== undefined) {
    conditions.push(`c.score >= $${paramIdx}`)
    values.push(min_score)
    paramIdx += 1
  }

  const whereClause = conditions.join(' AND ')

  const client = await pool.connect()
  try {
    const countRes = await client.query(
      `SELECT COUNT(*)::int AS total
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE ${whereClause}`,
      values
    )
    const total: number = countRes.rows[0]?.total ?? 0
    const total_pages = total > 0 ? Math.ceil(total / limit) : 0
    const offset = (page - 1) * limit

    const dataRes = await client.query(
      `SELECT
         c.id, c.job_id, c.title, c.score, c.start_time, c.end_time,
         LEFT(v.transcript, 500) AS transcript,
         c.created_at
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE ${whereClause}
       ORDER BY ${orderBy}
       LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`,
      [...values, limit, offset]
    )

    const items = dataRes.rows.map((r: Record<string, unknown>) => ({
      id: r.id,
      job_id: r.job_id,
      title: r.title,
      score: r.score !== null && r.score !== undefined ? Number(r.score) : null,
      start_time: Number(r.start_time),
      end_time: Number(r.end_time),
      transcript: (r.transcript as string | null) ?? null,
      created_at: new Date(r.created_at as string).toISOString(),
    }))

    return res.json({ items, total, page, limit, total_pages })
  } catch (err) {
    console.error('GET /clips error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})
