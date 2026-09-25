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
    // Validación de jobId nulo/vacío/inválido antes de pedir al backend
    const trimmed = jobId.trim()
    if (!trimmed || trimmed === 'null' || trimmed === 'undefined') {
      console.error('[useJobPolling] jobId inválido:', jobId)
      try { localStorage.removeItem('clipsai_active_job_id') } catch {}
      if (mountedRef.current) {
        setError('Identificador de job inválido. Redirigiendo a subida...')
        setPollingStatus('error')
      }
      return undefined
    }
    try {
      const res = await jobService.getJobStatus(trimmed)
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
      // 401 durante polling de job: no mostrar alerta intrusiva, reintentar silenciosamente en segundo plano
      // (JWT extendido a 1440 min mitiga vencimiento durante procesamiento largo)
      const status = err instanceof ApiError ? err.status : 0
      if (status === 401) {
        // Intentar refrescar token silenciosamente: re-leer desde localStorage (si fue renovado por otra pestaña/auth)
        // Mantener UI de progreso sin interrupción
        console.warn('[useJobPolling] 401 en polling job, reintentando sin mostrar error')
        setPollingStatus('polling')
        // No setear error para evitar alerta roja bloqueante
        return undefined
      }
      // 404/500: job no existe o error servidor → limpiar localStorage y no bloquear UI con spinner
      if (status === 404 || status >= 500) {
        console.error('[useJobPolling] Error al restaurar sesión del job:', err)
        try { localStorage.removeItem('clipsai_active_job_id') } catch {}
        const msg = status === 404 ? 'Job no encontrado. Puede haber expirado o ser inválido.' : 'Error del servidor al consultar el job.'
        if (mountedRef.current) {
          setError(msg)
          setPollingStatus('error')
        }
        return undefined
      }
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
