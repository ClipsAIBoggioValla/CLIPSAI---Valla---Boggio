import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const statsRouter = Router()

statsRouter.get('/summary', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id

  const client = await pool.connect()
  try {
    const totalVideosRes = await client.query(
      'SELECT COUNT(*)::int AS count FROM videos WHERE usuario_id = $1',
      [userId]
    )
    const total_videos: number = totalVideosRes.rows[0]?.count ?? 0

    const aggRes = await client.query(
      `
      SELECT
        COUNT(c.id)::int AS total_clips,
        AVG(c.score) AS avg_score,
        COUNT(CASE WHEN c.score >= 0 AND c.score <= 40 THEN 1 END)::int AS low,
        COUNT(CASE WHEN c.score >= 41 AND c.score <= 70 THEN 1 END)::int AS medium,
        COUNT(CASE WHEN c.score >= 71 AND c.score <= 100 THEN 1 END)::int AS high
      FROM clips c
      WHERE c.video_id IN (SELECT id FROM videos WHERE usuario_id = $1)
      `,
      [userId]
    )
    const agg = aggRes.rows[0] ?? { total_clips: 0, avg_score: null, low: 0, medium: 0, high: 0 }
    const total_clips: number = Number(agg.total_clips ?? 0)
    const rawAvg = agg.avg_score
    const avg_score: number = rawAvg !== null && rawAvg !== undefined ? Math.round(Number(rawAvg) * 10) / 10 : 0.0
    const estimated_time_saved_minutes: number = total_clips * 15

    const score_distribution = [
      { range: '0-40', count: Number(agg.low ?? 0), label: 'Bajo' },
      { range: '41-70', count: Number(agg.medium ?? 0), label: 'Medio' },
      { range: '71-100', count: Number(agg.high ?? 0), label: 'Alto' },
    ]

    const recentRes = await client.query(
      `
      SELECT j.id, j.status, j.created_at
      FROM jobs j
      JOIN videos v ON j.video_id = v.id
      WHERE v.usuario_id = $1
      ORDER BY j.created_at DESC
      LIMIT 1
      `,
      [userId]
    )
    let recent_job: { id: string; status: string; created_at: string } | null = null
    if (recentRes.rows[0]) {
      const r = recentRes.rows[0] as { id: string; status: string; created_at: string }
      recent_job = {
        id: r.id,
        status: String(r.status).toUpperCase(),
        created_at: new Date(r.created_at).toISOString(),
      }
    }

    return res.json({
      total_videos,
      total_clips,
      avg_score,
      estimated_time_saved_minutes,
      score_distribution,
      recent_job,
    })
  } catch (err) {
    console.error('GET /stats/summary error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})
