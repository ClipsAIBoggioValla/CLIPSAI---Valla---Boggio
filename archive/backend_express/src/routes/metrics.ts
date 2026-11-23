import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const metricsRouter = Router()

const TOTAL_JOBS_SQL = `SELECT COUNT(j.id)::int AS count
   FROM jobs j
   JOIN videos v ON j.video_id = v.id
   WHERE v.usuario_id = $1`

const TOTAL_CLIPS_SQL = `SELECT COUNT(c.id)::int AS count
   FROM clips c
   JOIN jobs j ON c.job_id = j.id
   JOIN videos v ON j.video_id = v.id
   WHERE v.usuario_id = $1`

const TOTAL_SECONDS_SQL = `SELECT COALESCE(SUM(v.duration_seconds), 0) AS total_seconds
   FROM videos v
   WHERE v.usuario_id = $1`

const PLATFORM_SQL = `SELECT c.social_network, COUNT(c.id)::int AS count
   FROM clips c
   JOIN jobs j ON c.job_id = j.id
   JOIN videos v ON j.video_id = v.id
   WHERE v.usuario_id = $1
   GROUP BY c.social_network`

const JOBS_BY_DAY_SQL = `SELECT (j.created_at::date)::text AS d, COUNT(j.id)::int AS count
   FROM jobs j
   JOIN videos v ON j.video_id = v.id
   WHERE v.usuario_id = $1 AND (j.created_at::date) >= $2::date
   GROUP BY d`

const CLIPS_BY_DAY_SQL = `SELECT (c.created_at::date)::text AS d, COUNT(c.id)::int AS count
   FROM clips c
   JOIN jobs j ON c.job_id = j.id
   JOIN videos v ON j.video_id = v.id
   WHERE v.usuario_id = $1 AND (c.created_at::date) >= $2::date
   GROUP BY d`

const MINUTES_BY_DAY_SQL = `SELECT (v.created_at::date)::text AS d, COALESCE(SUM(v.duration_seconds),0) AS total_seconds
   FROM videos v
   WHERE v.usuario_id = $1 AND (v.created_at::date) >= $2::date
   GROUP BY d`

async function scalarCount(client: import('pg').PoolClient, sql: string, userId: string): Promise<number> {
  const res = await client.query(sql, [userId])
  return res.rows[0]?.count ?? 0
}

async function totalMinutesProcessed(client: import('pg').PoolClient, userId: string): Promise<number> {
  const minutesRes = await client.query(TOTAL_SECONDS_SQL, [userId])
  const totalSeconds = Number(minutesRes.rows[0]?.total_seconds ?? 0)
  return Math.round((totalSeconds / 60) * 100) / 100
}

function timeSavedHours(total_minutes_processed: number, total_clips: number): number {
  if (total_minutes_processed > 0) return Math.round((total_minutes_processed * 3 / 60) * 100) / 100
  return Math.round((total_clips * 15 / 60) * 100) / 100
}

function emptyPlatformDistribution(): Record<string, number> {
  return {
    tiktok: 0,
    youtube: 0,
    instagram: 0,
  }
}

function isYouTubeNetwork(s: string): boolean {
  return s === 'youtube' || s === 'youtube_shorts'
}

function isInstagramNetwork(s: string): boolean {
  return s === 'instagram' || s === 'instagram_reels'
}

function addUnknownPlatform(distribution: Record<string, number>, s: string, count: number): void {
  distribution[s] = (distribution[s] ?? 0) + count
}

function applyPlatformCount(distribution: Record<string, number>, s: string, count: number): void {
  if (s === 'tiktok') distribution.tiktok += count
  else if (isYouTubeNetwork(s)) distribution.youtube += count
  else if (isInstagramNetwork(s)) distribution.instagram += count
  else addUnknownPlatform(distribution, s, count)
}

function countPlatformRow(distribution: Record<string, number>, row: { social_network: string | null; count: number }): void {
  if (!row.social_network) return
  applyPlatformCount(distribution, String(row.social_network).toLowerCase(), Number(row.count))
}

async function platformDistribution(client: import('pg').PoolClient, userId: string): Promise<Record<string, number>> {
  const platformRes = await client.query(PLATFORM_SQL, [userId])
  const distribution = emptyPlatformDistribution()
  for (const row of platformRes.rows as Array<{ social_network: string | null; count: number }>) {
    countPlatformRow(distribution, row)
  }
  return distribution
}

function last7DayRange(): { startDate: Date; startDateStr: string } {
  const today = new Date()
  const todayUtc = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()))
  const startDate = new Date(todayUtc)
  startDate.setUTCDate(todayUtc.getUTCDate() - 6)
  const startDateStr = startDate.toISOString().slice(0, 10)
  return { startDate, startDateStr }
}

function dayCountMap(rows: Array<{ d: string; count: number }>): Map<string, number> {
  const map = new Map<string, number>()
  for (const r of rows) {
    map.set(r.d, Number(r.count))
  }
  return map
}

function minutesByDayMap(rows: Array<{ d: string; total_seconds: string }>): Map<string, number> {
  const map = new Map<string, number>()
  for (const r of rows) {
    const mins = Math.round((Number(r.total_seconds) / 60) * 100) / 100
    map.set(r.d, mins)
  }
  return map
}

async function fetchDayCounts(client: import('pg').PoolClient, sql: string, userId: string, startDateStr: string): Promise<Map<string, number>> {
  const res = await client.query(sql, [userId, startDateStr])
  return dayCountMap(res.rows as Array<{ d: string; count: number }>)
}

async function fetchMinutesByDay(client: import('pg').PoolClient, sql: string, userId: string, startDateStr: string): Promise<Map<string, number>> {
  const res = await client.query(sql, [userId, startDateStr])
  return minutesByDayMap(res.rows as Array<{ d: string; total_seconds: string }>)
}

interface ActivityEntry {
  date: string
  jobs: number
  clips: number
  minutes_processed: number
}

function recentActivityEntry(startDate: Date, i: number, jobsMap: Map<string, number>, clipsMap: Map<string, number>, minutesMap: Map<string, number>): ActivityEntry {
  const d = new Date(startDate)
  d.setUTCDate(startDate.getUTCDate() + i)
  const dStr = d.toISOString().slice(0, 10)
  return {
    date: dStr,
    jobs: jobsMap.get(dStr) ?? 0,
    clips: clipsMap.get(dStr) ?? 0,
    minutes_processed: minutesMap.get(dStr) ?? 0,
  }
}

function buildRecentActivity(startDate: Date, jobsMap: Map<string, number>, clipsMap: Map<string, number>, minutesMap: Map<string, number>): ActivityEntry[] {
  const recent_activity: ActivityEntry[] = []
  for (let i = 0; i < 7; i++) {
    recent_activity.push(recentActivityEntry(startDate, i, jobsMap, clipsMap, minutesMap))
  }
  return recent_activity
}

async function handleMetrics(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const client = await pool.connect()
  try {
    const total_jobs: number = await scalarCount(client, TOTAL_JOBS_SQL, userId)
    const total_clips: number = await scalarCount(client, TOTAL_CLIPS_SQL, userId)
    const total_minutes_processed: number = await totalMinutesProcessed(client, userId)
    const time_saved_hours: number = timeSavedHours(total_minutes_processed, total_clips)
    const platform_distribution: Record<string, number> = await platformDistribution(client, userId)
    const { startDate, startDateStr } = last7DayRange()
    const jobsMap = await fetchDayCounts(client, JOBS_BY_DAY_SQL, userId, startDateStr)
    const clipsMap = await fetchDayCounts(client, CLIPS_BY_DAY_SQL, userId, startDateStr)
    const minutesMap = await fetchMinutesByDay(client, MINUTES_BY_DAY_SQL, userId, startDateStr)
    const recent_activity = buildRecentActivity(startDate, jobsMap, clipsMap, minutesMap)
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
