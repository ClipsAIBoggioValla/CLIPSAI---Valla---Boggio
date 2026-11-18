import { Router } from 'express'
import multer from 'multer'
import fs from 'fs'
import path from 'path'
import { randomUUID } from 'crypto'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'
import { runJob } from './jobs.js'

export const videosRouter = Router()

const ALLOWED_VIDEO = new Set(['.mp4', '.mov', '.avi'])
const ALLOWED_TRANSCRIPT = new Set(['.txt', '.srt'])
const MAX_SIZE = 500 * 1024 * 1024

function getUploadDir(): string {
  const candidates = [process.env.UPLOAD_DIR ?? '/storage/uploads', path.join(process.cwd(), 'storage', 'uploads')]
  for (const p of candidates) {
    try {
      fs.mkdirSync(p, { recursive: true })
      return p
    } catch {}
  }
  const fallback = path.join(process.cwd(), 'storage', 'uploads')
  fs.mkdirSync(fallback, { recursive: true })
  return fallback
}

const storage = multer.diskStorage({
  destination(_req, _file, cb) {
    cb(null, getUploadDir())
  },
  filename(_req, file, cb) {
    const ext = path.extname(file.originalname).toLowerCase()
    cb(null, `${randomUUID().replace(/-/g, '')}${ext}`)
  },
})

function fileFilter(_req: unknown, file: Express.Multer.File, cb: multer.FileFilterCallback) {
  const ext = path.extname(file.originalname).toLowerCase()
  if (file.fieldname === 'video' && !ALLOWED_VIDEO.has(ext)) {
    return cb(new Error(`video: extension no permitida '${ext}'. Permitidas: ${[...ALLOWED_VIDEO].join(', ')}`))
  }
  if (file.fieldname === 'transcription' && !ALLOWED_TRANSCRIPT.has(ext)) {
    return cb(new Error(`transcription: extension no permitida '${ext}'. Permitidas: ${[...ALLOWED_TRANSCRIPT].join(', ')}`))
  }
  cb(null, true)
}

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: MAX_SIZE },
})

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

function discardUploadedFile(pathValue: string | undefined): void {
  if (!pathValue) return
  try { fs.unlinkSync(pathValue) } catch {}
}

function readTranscriptText(transcriptFile: Express.Multer.File | undefined): string | null {
  if (!transcriptFile) return null
  try {
    return fs.readFileSync(transcriptFile.path, 'utf-8').slice(0, 50000)
  } catch {
    return null
  }
}

async function insertVideo(userId: string, videoFile: Express.Multer.File, transcriptFile: Express.Multer.File | undefined, transcriptText: string | null): Promise<Record<string, unknown>> {
  const r = await pool.query(
    'INSERT INTO videos (usuario_id, original_filename, file_path, transcription_filepath, transcript) VALUES ($1,$2,$3,$4,$5) RETURNING id, original_filename AS filename, created_at',
    [userId, videoFile.originalname || videoFile.filename, videoFile.path, transcriptFile?.path ?? null, transcriptText]
  )
  return r.rows[0] as Record<string, unknown>
}

function videoResponse(row: Record<string, unknown>): Record<string, unknown> {
  return { id: row.id, filename: row.filename, created_at: new Date(row.created_at as string).toISOString() }
}

videosRouter.post(
  '/',
  authMiddleware,
  upload.fields([
    { name: 'video', maxCount: 1 },
    { name: 'transcription', maxCount: 1 },
  ]),
  async (req: AuthRequest, res) => {
    const userId = req.user!.id
    if (!isValidUuid(userId)) return res.status(401).json({ detail: 'Usuario inválido' })

    const files = req.files as Record<string, Express.Multer.File[]> | undefined
    const videoFile = files?.video?.[0]
    const transcriptFile = files?.transcription?.[0]

    if (!videoFile) {
      discardUploadedFile(transcriptFile?.path)
      return res.status(400).json({ detail: 'Se requiere archivo de video' })
    }

    const transcriptText = readTranscriptText(transcriptFile)

    try {
      const row = await insertVideo(userId, videoFile, transcriptFile, transcriptText)
      return res.status(201).json(videoResponse(row))
    } catch (err) {
      discardUploadedFile(videoFile.path)
      discardUploadedFile(transcriptFile?.path)
      console.error('POST /videos error', err)
      return res.status(500).json({ detail: 'Error interno' })
    }
  }
)

/**
 * POST /videos/sample — Crear job con video de muestra (Issue 34)
 * Copia el video de muestra al directorio de uploads, crea video + job y lo ejecuta en background.
 * Responde 202 con JobResponse (id, video_id, status, progress, ...).
 */
function sampleVideoCandidates(): string[] {
  return [
    path.join(process.cwd(), 'backend_fastapi', 'storage', 'sample', 'sample.mp4'),
    path.join(process.cwd(), '..', 'backend_fastapi', 'storage', 'sample', 'sample.mp4'),
    path.join(process.cwd(), 'storage', 'sample', 'sample.mp4'),
    path.join(process.cwd(), '..', 'storage', 'sample', 'sample.mp4'),
  ]
}

function existingSamplePath(candidates: string[]): string | null {
  for (const c of candidates) {
    if (fs.existsSync(c)) return c
  }
  return null
}

/** Resolver ruta del video de muestra (igual que FastAPI) */
function resolveSamplePath(): string | null {
  const envPath = (process.env.SAMPLE_VIDEO_PATH || '').trim()
  if (envPath) {
    const p = path.resolve(envPath)
    if (fs.existsSync(p)) return p
  }
  const candidates = sampleVideoCandidates()
  return existingSamplePath(candidates) ?? candidates[0]
}

function missingSampleError(samplePath: string | null): { status: number; detail: string } | null {
  if (samplePath && fs.existsSync(samplePath)) return null
  return {
    status: 404,
    detail: `Video de muestra no encontrado en ${samplePath}. Colocá un archivo sample.mp4 en esa ubicación o configurá SAMPLE_VIDEO_PATH.`,
  }
}

function copySampleVideo(samplePath: string): string | null {
  const uploadDir = getUploadDir()
  const dest = path.join(uploadDir, `sample_${randomUUID().replace(/-/g, '')}.mp4`)
  try {
    fs.copyFileSync(samplePath, dest)
    return dest
  } catch (err) {
    console.error('Error copiando video de muestra:', err)
    return null
  }
}

async function insertSampleVideo(userId: string, dest: string): Promise<string | null> {
  try {
    const r = await pool.query(
      'INSERT INTO videos (usuario_id, original_filename, file_path, transcript) VALUES ($1,$2,$3,$4) RETURNING id',
      [userId, 'sample.mp4', dest, null]
    )
    return r.rows[0].id as string
  } catch (err) {
    console.error('Error insertando video muestra:', err)
    try { fs.unlinkSync(dest) } catch {}
    return null
  }
}

async function insertSampleJob(videoId: string): Promise<string | null> {
  try {
    const r = await pool.query(
      'INSERT INTO jobs (video_id, status, progress) VALUES ($1, $2, $3) RETURNING id',
      [videoId, 'pending', 0]
    )
    return r.rows[0].id as string
  } catch (err) {
    console.error('Error creando job muestra:', err)
    // No borramos el video, queda para reintento
    return null
  }
}

function sampleResponse(jobId: string, videoId: string): Record<string, unknown> {
  // Responder 202 con JobResponse (paridad con FastAPI)
  return {
    id: jobId,
    video_id: videoId,
    status: 'PENDING',
    progress: 0,
    error_message: null,
    result_metadata: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}

async function createSampleVideoJob(userId: string, dest: string): Promise<{ jobId: string; videoId: string } | { status: number; detail: string }> {
  const videoId = await insertSampleVideo(userId, dest)
  if (!videoId) return { status: 500, detail: 'Error creando video' }
  const jobId = await insertSampleJob(videoId)
  if (!jobId) return { status: 500, detail: 'Error creando job' }
  return { jobId, videoId }
}

videosRouter.post(
  '/sample',
  authMiddleware,
  async (req: AuthRequest, res) => {
    const userId = req.user!.id
    if (!isValidUuid(userId)) return res.status(401).json({ detail: 'Usuario inválido' })

    const samplePath = resolveSamplePath()
    const missing = missingSampleError(samplePath)
    if (missing) return res.status(missing.status).json({ detail: missing.detail })

    // Copiar el video de muestra al directorio de uploads
    const dest = copySampleVideo(samplePath as string)
    if (!dest) return res.status(500).json({ detail: 'Error copiando video de muestra' })

    // Crear video + job y ejecutar en background
    const created = await createSampleVideoJob(userId, dest)
    if ('status' in created) return res.status(created.status).json({ detail: created.detail })

    // Ejecutar job en background (no await)
    runJob(created.jobId).catch((err) => console.error(`[sample] job ${created.jobId} falló:`, err))

    return res.status(202).json(sampleResponse(created.jobId, created.videoId))
  }
)

videosRouter.get('/', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  try {
    const r = await pool.query('SELECT id, original_filename AS filename, created_at FROM videos WHERE usuario_id = $1 ORDER BY created_at DESC', [userId])
    const items = r.rows.map((row: Record<string, unknown>) => ({
      id: row.id,
      filename: row.filename,
      created_at: new Date(row.created_at as string).toISOString(),
    }))
    return res.json(items)
  } catch (err) {
    console.error('GET /videos error', err)
    return res.status(500).json({ detail: 'Error interno' })
  }
})

videosRouter.use((err: unknown, _req: unknown, res: import('express').Response, _next: import('express').NextFunction) => {
  const e = err as { message?: string; code?: string }
  if (e?.code === 'LIMIT_FILE_SIZE') return res.status(400).json({ detail: "Archivo supera el tamaño máximo de 500MB" })
  if (e?.message) return res.status(400).json({ detail: e.message })
  return res.status(500).json({ detail: 'Error interno' })
})
