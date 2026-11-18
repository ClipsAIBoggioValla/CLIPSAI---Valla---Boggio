import { Router } from 'express'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

function isTagBag(tags: unknown): tags is Record<string, unknown> {
  return Boolean(tags && typeof tags === 'object' && !Array.isArray(tags))
}

function stringAttr(obj: Record<string, unknown>, key: string): string | null {
  const v = obj[key]
  return typeof v === 'string' && v ? v : null
}

function transcriptAttrOf(row: Record<string, unknown>): string | null {
  for (const attr of ['transcript', 'transcript_text', 'transcription', 'text']) {
    const v = stringAttr(row, attr)
    if (v) return v
  }
  return null
}

function tagTranscriptOf(tags: unknown): string | null {
  if (!isTagBag(tags)) return null
  const fromTranscript = stringAttr(tags, 'transcript')
  if (fromTranscript) return fromTranscript
  return stringAttr(tags, 'text')
}

function videoTranscriptOf(row: Record<string, unknown>): string | null {
  return stringAttr(row as Record<string, unknown>, 'video_transcript')
}

function resolveTranscript(row: Record<string, unknown>): string {
  const attr = transcriptAttrOf(row)
  if (attr) return attr
  const tag = tagTranscriptOf(row.tags)
  if (tag) return tag
  return videoTranscriptOf(row) ?? ''
}

function escapeCsvField(value: string): string {
  if (value.includes('"') || value.includes(',') || value.includes('\n') || value.includes('\r')) {
    return '"' + value.replace(/"/g, '""') + '"'
  }
  return value
}

function csvScore(value: unknown): string {
  return value !== null && value !== undefined ? String(value) : ''
}

function buildCsv(rows: Record<string, unknown>[]): string {
  const header = ['ID', 'Título', 'Inicio', 'Fin', 'Score', 'Transcripción'].map(escapeCsvField).join(',')
  const lines = [header]
  for (const r of rows) {
    const transcript = resolveTranscript(r)
    const fields = [
      String(r.id),
      (r.title as string | null) ?? '',
      String(r.start_time),
      String(r.end_time),
      csvScore(r.score),
      transcript,
    ].map(escapeCsvField)
    lines.push(fields.join(','))
  }
  return lines.join('\n') + '\n'
}

function jsonScore(value: unknown): number | null {
  return value !== null && value !== undefined ? Number(value) : null
}

function buildJsonPayload(rows: Record<string, unknown>[], jobId?: string): Record<string, unknown> {
  const clips = rows.map((r) => ({
    id: String(r.id),
    title: (r.title as string | null) ?? null,
    start_time: Number(r.start_time),
    end_time: Number(r.end_time),
    score: jsonScore(r.score),
    transcript: resolveTranscript(r),
  }))
  const payload: Record<string, unknown> = {
    total_clips: clips.length,
    clips,
  }
  if (jobId) payload.job_id = jobId
  const scores = rows.map((r) => r.score).filter((s) => s !== null && s !== undefined).map(Number).filter((n) => !Number.isNaN(n))
  if (scores.length > 0) {
    payload.avg_score = Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100) / 100
  }
  return payload
}

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

function exportFormatError(format: string): string | null {
  if (format !== 'csv' && format !== 'json') return "format debe ser 'csv' o 'json'"
  return null
}

function sendCsvExport(res: import('express').Response, rows: Record<string, unknown>[]): import('express').Response {
  const csv = buildCsv(rows)
  res.setHeader('Content-Type', 'text/csv; charset=utf-8')
  res.setHeader('Content-Disposition', 'attachment; filename="clips_export.csv"')
  return res.send(csv)
}

function sendJsonExport(res: import('express').Response, rows: Record<string, unknown>[], jobId?: string): import('express').Response {
  const payload = buildJsonPayload(rows, jobId)
  const json = JSON.stringify(payload, null, 2)
  res.setHeader('Content-Type', 'application/json')
  res.setHeader('Content-Disposition', 'attachment; filename="clips_export.json"')
  return res.send(json)
}

function sendExport(res: import('express').Response, rows: Record<string, unknown>[], format: string, jobId?: string): import('express').Response {
  return format === 'csv' ? sendCsvExport(res, rows) : sendJsonExport(res, rows, jobId)
}

async function loadJobClips(client: import('pg').PoolClient, jobId: string) {
  return client.query(
    `SELECT c.id, c.title, c.start_time, c.end_time, c.score, c.tags,
            v.transcript AS video_transcript
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE c.job_id = $1
     ORDER BY c.start_time ASC`,
    [jobId]
  )
}

async function loadUserClips(client: import('pg').PoolClient, userId: string) {
  return client.query(
    `SELECT c.id, c.title, c.start_time, c.end_time, c.score, c.tags,
            v.transcript AS video_transcript
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE v.usuario_id = $1
     ORDER BY c.start_time ASC`,
    [userId]
  )
}

function jobExportParams(req: AuthRequest): { jobId: string; format: string } {
  const jobId = String(req.params.jobId ?? req.params.job_id ?? '')
  const format = String(req.query.format ?? '')
  return { jobId, format }
}

function jobExportParamError(jobId: string, format: string): { status: number; detail: string } | null {
  if (!isValidUuid(jobId)) return { status: 422, detail: 'job_id debe ser UUID válido' }
  const formatError = exportFormatError(format)
  if (formatError) return { status: 422, detail: formatError }
  return null
}

async function jobOwnershipError(client: import('pg').PoolClient, jobId: string, userId: string): Promise<{ status: number; detail: string } | null> {
  const jobRes = await client.query(
    `SELECT j.id, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1`,
    [jobId]
  )
  if (jobRes.rows.length === 0) return { status: 404, detail: 'Job no encontrado' }
  if (String(jobRes.rows[0].usuario_id) !== String(userId)) return { status: 404, detail: 'Job no encontrado' }
  return null
}

async function handleJobExport(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const { jobId, format } = jobExportParams(req)
  const paramError = jobExportParamError(jobId, format)
  if (paramError) return res.status(paramError.status).json({ detail: paramError.detail })

  const client = await pool.connect()
  try {
    const denied = await jobOwnershipError(client, jobId, userId)
    if (denied) return res.status(denied.status).json({ detail: denied.detail })
    const rows = (await loadJobClips(client, jobId)).rows as Record<string, unknown>[]
    return sendExport(res, rows, format, jobId)
  } catch (err) {
    console.error('export job error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
}

async function handleClipsExport(req: AuthRequest, res: import('express').Response) {
  const userId = req.user!.id
  const format = String(req.query.format ?? '')
  const formatError = exportFormatError(format)
  if (formatError) return res.status(422).json({ detail: formatError })

  const client = await pool.connect()
  try {
    const rows = (await loadUserClips(client, userId)).rows as Record<string, unknown>[]
    return sendExport(res, rows, format)
  } catch (err) {
    console.error('export clips error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
}

export const exportRouter = Router()

exportRouter.get('/clips/export', authMiddleware, handleClipsExport)
exportRouter.get('/jobs/:jobId/export', authMiddleware, handleJobExport)
exportRouter.get('/api/v1/jobs/:jobId/export', authMiddleware, handleJobExport)
