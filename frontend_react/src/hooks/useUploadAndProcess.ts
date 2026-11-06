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

    try {
      // ---- 1. Subir video + transcripción ----
      setPhase('uploading')
      const uploadedVideo = await videoService.upload(videoFile, transcriptFile)
      if (abortRef.current) return
      setVideo(uploadedVideo)

      // ---- 2. Crear Job (202 inmediato) ----
      setPhase('creating_job')
      const createdJob = await jobService.createJob(uploadedVideo.id)
      if (abortRef.current) return
      setJob(createdJob)

      // ---- 3. Polling hasta COMPLETED / FAILED ----
      setPhase('polling')
      const deadline = Date.now() + POLL_TIMEOUT_MS

      while (Date.now() < deadline) {
        if (abortRef.current) return

        await sleep(POLL_INTERVAL_MS)
        if (abortRef.current) return

        const statusRes = await jobService.getJobStatus(getJobId(createdJob))
        setJob(statusRes)

        const upperStatus = statusRes.status.toUpperCase()
        if (upperStatus === 'COMPLETED') {
          setPhase('completed')
          return
        }
        if (upperStatus === 'FAILED') {
          setPhase('failed')
          setError(statusRes.error_message ?? 'El job de procesamiento falló.')
          return
        }
      }

      // Timeout
      setPhase('failed')
      setError('Tiempo de espera agotado. El procesamiento demora más de lo esperado.')
    } catch (err: unknown) {
      if (abortRef.current) return
      setPhase('failed')
      if (err && typeof err === 'object' && 'detail' in err) {
        setError((err as { detail: string }).detail)
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Error inesperado')
      }
    }
  }, [])

  return { phase, video, job, error, run, reset }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
