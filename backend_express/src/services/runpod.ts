/**
 * Cliente HTTP para RunPod Serverless — port 1:1 de
 * `backend_fastapi/app/services/runpod_service.py`.
 */

export class RunPodError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RunPodError'
  }
}

interface RunPodSettings {
  apiKey: string
  endpointId: string
  requestTimeoutMs: number
  totalTimeoutSec: number
  pollIntervalSec: number
  apiBase: string
}

function settings(endpointId?: string): RunPodSettings {
  const apiKey = (process.env.RUNPOD_API_KEY || '').trim()
  const resolvedEndpointId = (endpointId || process.env.RUNPOD_ENDPOINT_ID || '').trim()
  if (!apiKey) throw new RunPodError('RUNPOD_API_KEY no está configurada')
  if (!resolvedEndpointId) throw new RunPodError('RUNPOD_ENDPOINT_ID no está configurado')

  const requestTimeoutSec = Number(process.env.RUNPOD_REQUEST_TIMEOUT_SECONDS || '95')
  const totalTimeoutSec = Number(process.env.RUNPOD_TIMEOUT_SECONDS || '1800')
  const pollIntervalSec = Number(process.env.RUNPOD_POLL_INTERVAL_SECONDS || '2')
  if (![requestTimeoutSec, totalTimeoutSec, pollIntervalSec].every((n) => Number.isFinite(n) && n > 0)) {
    throw new RunPodError('La configuración de timeouts de RunPod no es válida')
  }
  const apiBase = (process.env.RUNPOD_API_BASE_URL || 'https://api.runpod.ai/v2').replace(/\/+$/, '')
  return { apiKey, endpointId: resolvedEndpointId, requestTimeoutMs: requestTimeoutSec * 1000, totalTimeoutSec, pollIntervalSec, apiBase }
}

async function decodeResponse(resp: Response): Promise<Record<string, unknown>> {
  const text = await resp.text()
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new RunPodError(`RunPod devolvió una respuesta que no es JSON (HTTP ${resp.status}): ${text.slice(0, 500)}`)
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new RunPodError('RunPod devolvió una respuesta JSON inesperada')
  }
  return data as Record<string, unknown>
}

function raiseForJobFailure(data: Record<string, unknown>): void {
  const status = String(data.status || '').toUpperCase()
  if (['FAILED', 'CANCELLED', 'TIMED_OUT'].includes(status)) {
    const error = data.error || data.output || 'sin detalle'
    throw new RunPodError(`El job de RunPod terminó con estado ${status}: ${error}`)
  }
}

function resultFrom(data: Record<string, unknown>, jobId?: string): Record<string, unknown> {
  const output = data.output
  if (output && typeof output === 'object' && !Array.isArray(output)) return output as Record<string, unknown>
  return { output: output ?? null, job_id: jobId ?? data.id ?? null, status: String(data.status || '').toUpperCase() }
}

export interface ProcessVideoOptions {
  transcriptionUrl?: string | null
  transcriptionText?: string | null
  videoId?: string | null
  endpointId?: string | null
}

export async function processVideoViaRunpod(videoUrl: string, opts: ProcessVideoOptions = {}): Promise<Record<string, unknown>> {
  const url = typeof videoUrl === 'string' ? videoUrl.trim() : ''
  if (!url) throw new Error('video_url es obligatorio')
  if (opts.transcriptionUrl && opts.transcriptionText) {
    throw new Error('Envía transcription_url o transcription_text, no ambos')
  }

  const cfg = settings(opts.endpointId || undefined)
  const endpoint = `${cfg.apiBase}/${encodeURIComponent(cfg.endpointId)}/runsync`
  const headers = { Authorization: `Bearer ${cfg.apiKey}`, 'Content-Type': 'application/json' }
  const workerInput: Record<string, unknown> = { video_url: url }
  if (opts.transcriptionUrl) workerInput.transcription_url = opts.transcriptionUrl
  if (opts.transcriptionText !== undefined && opts.transcriptionText !== null) workerInput.transcription_text = opts.transcriptionText
  if (opts.videoId) workerInput.video_id = opts.videoId

  let data: Record<string, unknown>
  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify({ input: workerInput }),
      signal: AbortSignal.timeout(cfg.requestTimeoutMs),
    })
    if (!resp.ok) throw new RunPodError(`No se pudo llamar al endpoint de RunPod: HTTP ${resp.status}`)
    data = await decodeResponse(resp)
  } catch (err) {
    if (err instanceof RunPodError) throw err
    const e = err as Error
    if (e?.name === 'TimeoutError' || e?.name === 'AbortError') {
      throw new RunPodError(`Timeout esperando respuesta inicial de RunPod (${cfg.requestTimeoutMs / 1000}s)`)
    }
    throw new RunPodError(`No se pudo llamar al endpoint de RunPod: ${e?.message || err}`)
  }

  raiseForJobFailure(data)
  let status = String(data.status || '').toUpperCase()
  if (status === 'COMPLETED' || status === 'SUCCEEDED') return resultFrom(data)

  const jobId = data.id
  if (!jobId) throw new RunPodError(`Respuesta RunPod sin salida ni job id (status=${status || 'desconocido'})`)

  const deadline = Date.now() + cfg.totalTimeoutSec * 1000
  const statusUrl = `${cfg.apiBase}/${encodeURIComponent(cfg.endpointId)}/status/${encodeURIComponent(String(jobId))}`
  while (Date.now() < deadline) {
    const waitMs = Math.min(cfg.pollIntervalSec * 1000, Math.max(0, deadline - Date.now()))
    await new Promise((resolve) => setTimeout(resolve, waitMs))
    let polled: Record<string, unknown>
    try {
      const resp = await fetch(statusUrl, { headers, signal: AbortSignal.timeout(cfg.requestTimeoutMs) })
      if (!resp.ok) throw new RunPodError(`No se pudo consultar el job RunPod ${jobId}: HTTP ${resp.status}`)
      polled = await decodeResponse(resp)
    } catch (err) {
      if (err instanceof RunPodError) throw err
      const e = err as Error
      if (e?.name === 'TimeoutError' || e?.name === 'AbortError') {
        throw new RunPodError(`Timeout consultando el job RunPod ${jobId}`)
      }
      throw new RunPodError(`No se pudo consultar el job RunPod ${jobId}: ${e?.message || err}`)
    }
    raiseForJobFailure(polled)
    status = String(polled.status || '').toUpperCase()
    if (status === 'COMPLETED' || status === 'SUCCEEDED') return resultFrom(polled, String(jobId))
  }
  throw new RunPodError(`El job RunPod ${jobId} no terminó en ${cfg.totalTimeoutSec}s`)
}
