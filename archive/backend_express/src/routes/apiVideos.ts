import { Router } from 'express'
import { randomUUID } from 'crypto'
import path from 'path'
import { generatePresignedUrl } from '../services/s3.js'
import { RunPodError, processVideoViaRunpod } from '../services/runpod.js'

/**
 * Router `/api/videos` — paridad 1:1 con
 * `backend_fastapi/app/routers/videos.py` (`upload_url_router`).
 *
 *   POST /api/videos/upload-url → {upload_url, file_key}   (presigned PUT S3/R2, 900s)
 *   POST /api/videos/process    → resultado RunPod          (presigned GET si file_key)
 *
 * Ambos endpoints son públicos en FastAPI (sin CurrentUser).
 */
export const apiVideosRouter = Router()

function bodyOf(req: import('express').Request): Record<string, unknown> {
  return (req.body ?? {}) as Record<string, unknown>
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function missingFieldError(value: unknown, field: string): unknown[] {
  return typeof value !== 'string' || !value
    ? [{ loc: ['body', field], msg: 'field required', type: 'value_error.missing' }]
    : []
}

function uploadUrlValidationError(body: Record<string, unknown>): unknown[] {
  return [
    ...missingFieldError(body.file_name, 'file_name'),
    ...missingFieldError(body.file_type, 'file_type'),
  ]
}

apiVideosRouter.post('/upload-url', async (req, res) => {
  const body = bodyOf(req)
  const validation = uploadUrlValidationError(body)
  if (validation.length > 0) return res.status(422).json({ detail: validation })

  try {
    const ext = path.extname(body.file_name as string)
    const fileKey = `uploads/${randomUUID()}${ext}`
    const uploadUrl = generatePresignedUrl({
      method: 'PUT',
      key: fileKey,
      expiresIn: 900,
      contentType: body.file_type as string,
    })
    return res.json({ upload_url: uploadUrl, file_key: fileKey })
  } catch (err) {
    return res.status(500).json({ detail: `Error al generar la presigned URL: ${errorMessage(err)}` })
  }
})

function stringField(body: Record<string, unknown>, key: string): string {
  const v = body[key]
  return typeof v === 'string' ? v.trim() : ''
}

function optionalStringField(body: Record<string, unknown>, key: string): string | null {
  const v = body[key]
  return typeof v === 'string' ? v : null
}

function processValidationError(fileKey: string, rawVideoUrl: string, transcriptionUrl: string | null, transcriptionText: string | null): string | null {
  if (Boolean(fileKey) === Boolean(rawVideoUrl)) return 'Envía exactamente uno de file_key o video_url'
  if (transcriptionUrl && transcriptionText !== null) return 'Envía transcription_url o transcription_text, no ambos'
  return null
}

function presignReadUrl(fileKey: string): string {
  return generatePresignedUrl({ method: 'GET', key: fileKey, expiresIn: 3600 })
}

function runpodStatusCode(message: string): number {
  return /timeout|no terminó/i.test(message) ? 504 : 502
}

function processErrorResponse(res: import('express').Response, err: unknown): import('express').Response {
  if (err instanceof RunPodError) {
    return res.status(runpodStatusCode(err.message)).json({ detail: `Error al procesar con RunPod: ${err.message}` })
  }
  return res.status(422).json({ detail: errorMessage(err) })
}

apiVideosRouter.post('/process', async (req, res) => {
  const body = bodyOf(req)
  const fileKey = stringField(body, 'file_key')
  const rawVideoUrl = stringField(body, 'video_url')
  const transcriptionUrl = optionalStringField(body, 'transcription_url')
  const transcriptionText = optionalStringField(body, 'transcription_text')
  const videoId = optionalStringField(body, 'video_id')

  const validationError = processValidationError(fileKey, rawVideoUrl, transcriptionUrl, transcriptionText)
  if (validationError) return res.status(422).json({ detail: validationError })

  let videoUrl = rawVideoUrl
  if (fileKey) {
    try {
      videoUrl = presignReadUrl(fileKey)
    } catch (err) {
      return res.status(500).json({ detail: `Error al generar la presigned URL de lectura: ${errorMessage(err)}` })
    }
  }

  try {
    const result = await processVideoViaRunpod(videoUrl, {
      transcriptionUrl,
      transcriptionText,
      videoId,
    })
    return res.json(result)
  } catch (err) {
    return processErrorResponse(res, err)
  }
})
