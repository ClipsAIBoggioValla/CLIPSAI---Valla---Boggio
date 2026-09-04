import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const metricsRouter = Router()

async function handleMetrics(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const client = await pool.connect()
  try {
    const totalJobsRes = await client.query(
      `SELECT COUNT(j.id)::int AS count
       FROM jobs j
       JOIN videos v ON j.video_id = v.id
       WHERE v.usuario_id = $1`,
      [userId]
    )
    const total_jobs: number = totalJobsRes.rows[0]?.count ?? 0

    const totalClipsRes = await client.query(
      `SELECT COUNT(c.id)::int AS count
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE v.usuario_id = $1`,
      [userId]
    )
    const total_clips: number = totalClipsRes.rows[0]?.count ?? 0

    const minutesRes = await client.query(
      `SELECT COALESCE(SUM(v.duration_seconds), 0) AS total_seconds
       FROM videos v
       WHERE v.usuario_id = $1`,
      [userId]
    )
    const totalSeconds = Number(minutesRes.rows[0]?.total_seconds ?? 0)
    const total_minutes_processed: number = Math.round((totalSeconds / 60) * 100) / 100

    let time_saved_hours: number
    if (total_minutes_processed > 0) {
      time_saved_hours = Math.round((total_minutes_processed * 3 / 60) * 100) / 100
    } else {
      time_saved_hours = Math.round((total_clips * 15 / 60) * 100) / 100
    }

    const platformRes = await client.query(
      `SELECT c.social_network, COUNT(c.id)::int AS count
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE v.usuario_id = $1
       GROUP BY c.social_network`,
      [userId]
    )
    const platform_distribution: Record<string, number> = {
      tiktok: 0,
      youtube: 0,
      instagram: 0,
    }
    for (const row of platformRes.rows as Array<{ social_network: string | null; count: number }>) {
      if (!row.social_network) continue
      const s = String(row.social_network).toLowerCase()
      const c = Number(row.count)
      if (s === 'tiktok') platform_distribution.tiktok += c
      else if (s === 'youtube' || s === 'youtube_shorts') platform_distribution.youtube += c
      else if (s === 'instagram' || s === 'instagram_reels') platform_distribution.instagram += c
      else platform_distribution[s] = (platform_distribution[s] ?? 0) + c
    }

    const today = new Date()
    const todayUtc = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()))
    const startDate = new Date(todayUtc)
    startDate.setUTCDate(todayUtc.getUTCDate() - 6)
    const startDateStr = startDate.toISOString().slice(0, 10)

    const jobsByDayRes = await client.query(
      `SELECT (j.created_at::date)::text AS d, COUNT(j.id)::int AS count
       FROM jobs j
       JOIN videos v ON j.video_id = v.id
       WHERE v.usuario_id = $1 AND (j.created_at::date) >= $2::date
       GROUP BY d`,
      [userId, startDateStr]
    )
    const jobsMap = new Map<string, number>()
    for (const r of jobsByDayRes.rows as Array<{ d: string; count: number }>) {
      jobsMap.set(r.d, Number(r.count))
    }

    const clipsByDayRes = await client.query(
      `SELECT (c.created_at::date)::text AS d, COUNT(c.id)::int AS count
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE v.usuario_id = $1 AND (c.created_at::date) >= $2::date
       GROUP BY d`,
      [userId, startDateStr]
    )
    const clipsMap = new Map<string, number>()
    for (const r of clipsByDayRes.rows as Array<{ d: string; count: number }>) {
      clipsMap.set(r.d, Number(r.count))
    }

    const minutesByDayRes = await client.query(
      `SELECT (v.created_at::date)::text AS d, COALESCE(SUM(v.duration_seconds),0) AS total_seconds
       FROM videos v
       WHERE v.usuario_id = $1 AND (v.created_at::date) >= $2::date
       GROUP BY d`,
      [userId, startDateStr]
    )
    const minutesMap = new Map<string, number>()
    for (const r of minutesByDayRes.rows as Array<{ d: string; total_seconds: string }>) {
      const mins = Math.round((Number(r.total_seconds) / 60) * 100) / 100
      minutesMap.set(r.d, mins)
    }

    const recent_activity: Array<{ date: string; jobs: number; clips: number; minutes_processed: number }> = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(startDate)
      d.setUTCDate(startDate.getUTCDate() + i)
      const dStr = d.toISOString().slice(0, 10)
      recent_activity.push({
        date: dStr,
        jobs: jobsMap.get(dStr) ?? 0,
        clips: clipsMap.get(dStr) ?? 0,
        minutes_processed: minutesMap.get(dStr) ?? 0,
      })
    }

    return res.json({
      total_jobs,
      total_clips,
      total_minutes_processed,
      time_saved_hours,
      platform_distribution,
      recent_activity,
    })
  } catch (err) {
    console.error('GET /metrics error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
}

metricsRouter.get('/metrics', authMiddleware, handleMetrics)
metricsRouter.get('/api/metrics', authMiddleware, handleMetrics)
