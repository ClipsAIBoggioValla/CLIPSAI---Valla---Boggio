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

apiVideosRouter.post('/upload-url', async (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  const fileName = body.file_name
  const fileType = body.file_type

  if (typeof fileName !== 'string' || !fileName || typeof fileType !== 'string' || !fileType) {
    return res.status(422).json({
      detail: [
        ...(typeof fileName !== 'string' || !fileName ? [{ loc: ['body', 'file_name'], msg: 'field required', type: 'value_error.missing' }] : []),
        ...(typeof fileType !== 'string' || !fileType ? [{ loc: ['body', 'file_type'], msg: 'field required', type: 'value_error.missing' }] : []),
      ],
    })
  }

  try {
    const ext = path.extname(fileName)
    const fileKey = `uploads/${randomUUID()}${ext}`
    const uploadUrl = generatePresignedUrl({
      method: 'PUT',
      key: fileKey,
      expiresIn: 900,
      contentType: fileType,
    })
    return res.json({ upload_url: uploadUrl, file_key: fileKey })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return res.status(500).json({ detail: `Error al generar la presigned URL: ${message}` })
  }
})

apiVideosRouter.post('/process', async (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  const fileKey = typeof body.file_key === 'string' ? body.file_key.trim() : ''
  const rawVideoUrl = typeof body.video_url === 'string' ? body.video_url.trim() : ''
  const transcriptionUrl = typeof body.transcription_url === 'string' ? body.transcription_url : null
  const transcriptionText = typeof body.transcription_text === 'string' ? body.transcription_text : null
  const videoId = typeof body.video_id === 'string' ? body.video_id : null

  const hasFileKey = Boolean(fileKey)
  const hasVideoUrl = Boolean(rawVideoUrl)
  if (hasFileKey === hasVideoUrl) {
    return res.status(422).json({ detail: 'Envía exactamente uno de file_key o video_url' })
  }
  if (transcriptionUrl && transcriptionText !== null) {
    return res.status(422).json({ detail: 'Envía transcription_url o transcription_text, no ambos' })
  }

  let videoUrl = rawVideoUrl
  if (hasFileKey) {
    try {
      videoUrl = generatePresignedUrl({ method: 'GET', key: fileKey, expiresIn: 3600 })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      return res.status(500).json({ detail: `Error al generar la presigned URL de lectura: ${message}` })
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
    if (err instanceof RunPodError) {
      const message = err.message
      const statusCode = /timeout|no terminó/i.test(message) ? 504 : 502
      return res.status(statusCode).json({ detail: `Error al procesar con RunPod: ${message}` })
    }
    const message = err instanceof Error ? err.message : String(err)
    return res.status(422).json({ detail: message })
  }
})
