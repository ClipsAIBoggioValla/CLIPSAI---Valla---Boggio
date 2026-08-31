import { useCallback, useEffect, useRef, useState } from 'react'
import { jobService } from '@/services/api'
import { ApiError } from '@/types/api'
import type { JobResponse } from '@/types/api'

export type PollingStatus = 'idle' | 'polling' | 'completed' | 'failed' | 'error'

export interface UseJobPollingResult {
  job: JobResponse | null
  pollingStatus: PollingStatus
  error: string | null
  refresh: () => Promise<void>
}

const POLL_INTERVAL_MS = 2000

function isTerminal(status: string): boolean {
  const s = status.toUpperCase()
  return s === 'COMPLETED' || s === 'FAILED'
}

export function useJobPolling(jobId: string | undefined): UseJobPollingResult {
  const [job, setJob] = useState<JobResponse | null>(null)
  const [pollingStatus, setPollingStatus] = useState<PollingStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<number | null>(null)
  const mountedRef = useRef(true)

  const fetchOnce = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await jobService.getJobStatus(jobId)
      if (!mountedRef.current) return
      setJob(res)
      setError(null)
      const st = res.status.toUpperCase()
      if (st === 'COMPLETED') setPollingStatus('completed')
      else if (st === 'FAILED') setPollingStatus('failed')
      else setPollingStatus('polling')
      return res
    } catch (err) {
      if (!mountedRef.current) return
      const msg = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error al consultar el job'
      setError(msg)
      setPollingStatus('error')
      return undefined
    }
  }, [jobId])

  useEffect(() => {
    mountedRef.current = true
    if (!jobId) {
      setPollingStatus('idle')
      return
    }
    setPollingStatus('polling')
    void fetchOnce()

    timerRef.current = window.setInterval(() => {
      void (async () => {
        const res = await fetchOnce()
        if (res && isTerminal(res.status)) {
          if (timerRef.current !== null) {
            clearInterval(timerRef.current)
            timerRef.current = null
          }
        }
      })()
    }, POLL_INTERVAL_MS)

    return () => {
      mountedRef.current = false
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [jobId, fetchOnce])

  useEffect(() => {
    if (!job) return
    if (isTerminal(job.status) && timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [job])

  const refresh = useCallback(async () => {
    await fetchOnce()
  }, [fetchOnce])

  return { job, pollingStatus, error, refresh }
}
