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

function trimEnv(name: string, fallback: string): string {
  return (process.env[name] || fallback).trim()
}

function requireTrimmed(value: string, message: string): string {
  if (!value) throw new RunPodError(message)
  return value
}

function resolvedEndpointIdOf(endpointId?: string): string {
  return (endpointId || process.env.RUNPOD_ENDPOINT_ID || '').trim()
}

function timeoutSetting(name: string, fallback: string): number {
  return Number(process.env[name] || fallback)
}

function validTimeouts(requestTimeoutSec: number, totalTimeoutSec: number, pollIntervalSec: number): boolean {
  return [requestTimeoutSec, totalTimeoutSec, pollIntervalSec].every((n) => Number.isFinite(n) && n > 0)
}

function settings(endpointId?: string): RunPodSettings {
  const apiKey = requireTrimmed(trimEnv('RUNPOD_API_KEY', ''), 'RUNPOD_API_KEY no está configurada')
  const resolvedEndpointId = requireTrimmed(resolvedEndpointIdOf(endpointId), 'RUNPOD_ENDPOINT_ID no está configurado')
  const requestTimeoutSec = timeoutSetting('RUNPOD_REQUEST_TIMEOUT_SECONDS', '95')
  const totalTimeoutSec = timeoutSetting('RUNPOD_TIMEOUT_SECONDS', '1800')
  const pollIntervalSec = timeoutSetting('RUNPOD_POLL_INTERVAL_SECONDS', '2')
  if (!validTimeouts(requestTimeoutSec, totalTimeoutSec, pollIntervalSec)) {
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

function validOutput(output: unknown): boolean {
  return Boolean(output && typeof output === 'object' && !Array.isArray(output))
}

function jobIdOf(data: Record<string, unknown>, jobId?: string): string | null {
  return jobId ?? (data.id as string | null) ?? null
}

function statusUpper(data: Record<string, unknown>): string {
  return String(data.status || '').toUpperCase()
}

function resultFrom(data: Record<string, unknown>, jobId?: string): Record<string, unknown> {
  const output = data.output
  if (validOutput(output)) return output as Record<string, unknown>
  return { output: output ?? null, job_id: jobIdOf(data, jobId), status: statusUpper(data) }
}

export interface ProcessVideoOptions {
  transcriptionUrl?: string | null
  transcriptionText?: string | null
  videoId?: string | null
  endpointId?: string | null
}

function hasTranscriptionText(opts: ProcessVideoOptions): boolean {
  return opts.transcriptionText !== undefined && opts.transcriptionText !== null
}

function workerInputFor(url: string, opts: ProcessVideoOptions): Record<string, unknown> {
  const workerInput: Record<string, unknown> = { video_url: url }
  if (opts.transcriptionUrl) workerInput.transcription_url = opts.transcriptionUrl
  if (hasTranscriptionText(opts)) workerInput.transcription_text = opts.transcriptionText
  if (opts.videoId) workerInput.video_id = opts.videoId
  return workerInput
}

function requireVideoUrl(videoUrl: string, opts: ProcessVideoOptions): string {
  const url = typeof videoUrl === 'string' ? videoUrl.trim() : ''
  if (!url) throw new Error('video_url es obligatorio')
  if (opts.transcriptionUrl && opts.transcriptionText) {
    throw new Error('Envía transcription_url o transcription_text, no ambos')
  }
  return url
}

function isRunpodTerminal(status: string): boolean {
  return status === 'COMPLETED' || status === 'SUCCEEDED'
}

function runpodTimeoutError(e: Error): boolean {
  return e?.name === 'TimeoutError' || e?.name === 'AbortError'
}

function mapCallError(err: unknown, timeoutMessage: string, failurePrefix: string): RunPodError {
  if (err instanceof RunPodError) return err as RunPodError
  const e = err as Error
  if (runpodTimeoutError(e)) return new RunPodError(timeoutMessage)
  return new RunPodError(`${failurePrefix}: ${e?.message || err}`)
}

async function callRunpodEndpoint(endpoint: string, headers: Record<string, string>, workerInput: Record<string, unknown>, requestTimeoutMs: number): Promise<Record<string, unknown>> {
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers,
    body: JSON.stringify({ input: workerInput }),
    signal: AbortSignal.timeout(requestTimeoutMs),
  })
  if (!resp.ok) throw new RunPodError(`No se pudo llamar al endpoint de RunPod: HTTP ${resp.status}`)
  return decodeResponse(resp)
}

function requireJobId(data: Record<string, unknown>): string {
  const jobId = data.id
  if (!jobId) throw new RunPodError(`Respuesta RunPod sin salida ni job id (status=${statusUpper(data) || 'desconocido'})`)
  return String(jobId)
}

function mapPollError(jobId: string, err: unknown): RunPodError {
  if (err instanceof RunPodError) return err as RunPodError
  const e = err as Error
  if (runpodTimeoutError(e)) return new RunPodError(`Timeout consultando el job RunPod ${jobId}`)
  return new RunPodError(`No se pudo consultar el job RunPod ${jobId}: ${e?.message || err}`)
}

async function pollRunpodStatus(jobId: string, statusUrl: string, headers: Record<string, string>, cfg: RunPodSettings): Promise<Record<string, unknown>> {
  try {
    const resp = await fetch(statusUrl, { headers, signal: AbortSignal.timeout(cfg.requestTimeoutMs) })
    if (!resp.ok) throw new RunPodError(`No se pudo consultar el job RunPod ${jobId}: HTTP ${resp.status}`)
    return await decodeResponse(resp)
  } catch (err) {
    throw mapPollError(jobId, err)
  }
}

function pollWaitMs(cfg: RunPodSettings, deadline: number): number {
  return Math.min(cfg.pollIntervalSec * 1000, Math.max(0, deadline - Date.now()))
}

async function pollRunpodJob(jobId: string, headers: Record<string, string>, cfg: RunPodSettings, deadline: number): Promise<Record<string, unknown>> {
  const statusUrl = `${cfg.apiBase}/${encodeURIComponent(cfg.endpointId)}/status/${encodeURIComponent(jobId)}`
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, pollWaitMs(cfg, deadline)))
    const polled = await pollRunpodStatus(jobId, statusUrl, headers, cfg)
    raiseForJobFailure(polled)
    if (isRunpodTerminal(statusUpper(polled))) return resultFrom(polled, jobId)
  }
  throw new RunPodError(`El job RunPod ${jobId} no terminó en ${cfg.totalTimeoutSec}s`)
}

export async function processVideoViaRunpod(videoUrl: string, opts: ProcessVideoOptions = {}): Promise<Record<string, unknown>> {
  const url = requireVideoUrl(videoUrl, opts)
  const cfg = settings(opts.endpointId || undefined)
  const endpoint = `${cfg.apiBase}/${encodeURIComponent(cfg.endpointId)}/runsync`
  const headers = { Authorization: `Bearer ${cfg.apiKey}`, 'Content-Type': 'application/json' }
  const workerInput = workerInputFor(url, opts)

  let data: Record<string, unknown>
  try {
    data = await callRunpodEndpoint(endpoint, headers, workerInput, cfg.requestTimeoutMs)
  } catch (err) {
    throw mapCallError(err, `Timeout esperando respuesta inicial de RunPod (${cfg.requestTimeoutMs / 1000}s)`, 'No se pudo llamar al endpoint de RunPod')
  }

  raiseForJobFailure(data)
  if (isRunpodTerminal(statusUpper(data))) return resultFrom(data)

  const jobId = requireJobId(data)
  const deadline = Date.now() + cfg.totalTimeoutSec * 1000
  return pollRunpodJob(jobId, headers, cfg, deadline)
}
