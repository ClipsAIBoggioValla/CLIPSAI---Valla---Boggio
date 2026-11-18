// =============================================================================
// clipsai — Hook: flujo completo subida → creación de Job → polling
// =============================================================================
import { useCallback, useRef, useState } from 'react'
import { jobService, videoService } from '@/services/api'
import { getJobId } from '@/types/api'
import type { JobResponse, VideoUploadResponse } from '@/types/api'

export type UploadPhase =
  | 'idle'
  | 'uploading'
  | 'creating_job'
  | 'polling'
  | 'completed'
  | 'failed'

interface UseUploadAndProcessState {
  phase: UploadPhase
  video: VideoUploadResponse | null
  job: JobResponse | null
  error: string | null
}

interface UseUploadAndProcessActions {
  run: (videoFile: File, transcriptFile: File) => Promise<void>
  reset: () => void
}

export type UseUploadAndProcessResult = UseUploadAndProcessState & UseUploadAndProcessActions

const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 120_000

interface UploadFlowCtx {
  isAborted: () => boolean
  setPhase: (phase: UploadPhase) => void
  setVideo: (video: VideoUploadResponse | null) => void
  setJob: (job: JobResponse | null) => void
  setError: (error: string | null) => void
}

function hasDetail(err: unknown): boolean {
  return typeof err === 'object' && err !== null && 'detail' in err
}

function errorText(err: unknown): string {
  if (hasDetail(err)) return (err as { detail: string }).detail
  if (err instanceof Error) return err.message
  return 'Error inesperado'
}

async function startUploadAndCreateJob(
  ctx: UploadFlowCtx,
  videoFile: File,
  transcriptFile: File,
): Promise<JobResponse | null> {
  // ---- 1. Subir video + transcripción ----
  ctx.setPhase('uploading')
  const uploadedVideo = await videoService.upload(videoFile, transcriptFile)
  if (ctx.isAborted()) return null
  ctx.setVideo(uploadedVideo)

  // ---- 2. Crear Job (202 inmediato) ----
  ctx.setPhase('creating_job')
  const createdJob = await jobService.createJob(uploadedVideo.id)
  if (ctx.isAborted()) return null
  ctx.setJob(createdJob)

  // ---- 3. Polling hasta COMPLETED / FAILED ----
  ctx.setPhase('polling')
  return createdJob
}

async function pollStatusOnce(
  ctx: UploadFlowCtx,
  createdJob: JobResponse,
): Promise<'completed' | 'failed' | 'continue'> {
  const statusRes = await jobService.getJobStatus(getJobId(createdJob))
  ctx.setJob(statusRes)

  const upperStatus = statusRes.status.toUpperCase()
  if (upperStatus === 'COMPLETED') {
    ctx.setPhase('completed')
    return 'completed'
  }
  if (upperStatus === 'FAILED') {
    ctx.setPhase('failed')
    ctx.setError(statusRes.error_message ?? 'El job de procesamiento falló.')
    return 'failed'
  }
  return 'continue'
}

/** Un tick de polling. Devuelve true cuando el flujo terminó (abort o estado terminal). */
async function pollTick(ctx: UploadFlowCtx, createdJob: JobResponse): Promise<boolean> {
  if (ctx.isAborted()) return true

  await sleep(POLL_INTERVAL_MS)
  if (ctx.isAborted()) return true

  const outcome = await pollStatusOnce(ctx, createdJob)
  return outcome !== 'continue'
}

async function pollUntilTerminal(ctx: UploadFlowCtx, createdJob: JobResponse): Promise<void> {
  const deadline = Date.now() + POLL_TIMEOUT_MS

  while (Date.now() < deadline) {
    if (await pollTick(ctx, createdJob)) return
  }

  // Timeout
  ctx.setPhase('failed')
  ctx.setError('Tiempo de espera agotado. El procesamiento demora más de lo esperado.')
}

export function useUploadAndProcess(): UseUploadAndProcessResult {
  const [phase, setPhase] = useState<UploadPhase>('idle')
  const [video, setVideo] = useState<VideoUploadResponse | null>(null)
  const [job, setJob] = useState<JobResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef(false)

  const reset = useCallback(() => {
    abortRef.current = false
    setPhase('idle')
    setVideo(null)
    setJob(null)
    setError(null)
  }, [])

  const run = useCallback(async (videoFile: File, transcriptFile: File) => {
    abortRef.current = false
    setError(null)
    setVideo(null)
    setJob(null)

    const ctx: UploadFlowCtx = {
      isAborted: () => abortRef.current,
      setPhase,
      setVideo,
      setJob,
      setError,
    }

    try {
      const createdJob = await startUploadAndCreateJob(ctx, videoFile, transcriptFile)
      if (!createdJob) return
      await pollUntilTerminal(ctx, createdJob)
    } catch (err: unknown) {
      if (ctx.isAborted()) return
      ctx.setPhase('failed')
      ctx.setError(errorText(err))
    }
  }, [])

  return { phase, video, job, error, run, reset }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
