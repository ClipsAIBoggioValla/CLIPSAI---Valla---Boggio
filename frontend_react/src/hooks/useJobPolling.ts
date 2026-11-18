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

function isInvalidJobId(trimmed: string): boolean {
  return !trimmed || trimmed === 'null' || trimmed === 'undefined'
}

function pollFailureStatus(err: unknown): number {
  return err instanceof ApiError ? err.status : 0
}

function pollErrorMessage(err: unknown): string {
  return err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error al consultar el job'
}

type PollFailureKind = 'silent-retry' | 'unrecoverable' | 'generic'

function classifyPollFailure(status: number): PollFailureKind {
  if (status === 401) return 'silent-retry'
  if (status === 404 || status >= 500) return 'unrecoverable'
  return 'generic'
}

function unrecoverableMessage(status: number, err: unknown): string {
  console.error('[useJobPolling] Error al restaurar sesión del job:', err)
  try { localStorage.removeItem('clipsai_active_job_id') } catch {}
  return status === 404 ? 'Job no encontrado. Puede haber expirado o ser inválido.' : 'Error del servidor al consultar el job.'
}

interface PollStatusHooks {
  /** Recibe cada respuesta del backend y la expone en el estado. */
  onJob: (job: JobResponse) => void
  /** Transición de estado de polling (completed/failed/polling). */
  onStatus: (status: PollingStatus) => void
  /** Muestra un mensaje de error (y marca el polling como error). */
  fail: (msg: string) => void
  /** Limpia el error tras una consulta exitosa. */
  clearError: () => void
  /** Reintento silencioso (401): mantiene el progreso sin alerta intrusiva. */
  retrySilently: () => void
}

function handleUnrecoverablePollFailure(
  status: number,
  err: unknown,
  mounted: boolean,
  fail: (msg: string) => void,
): void {
  // 404/500: job no existe o error servidor → limpiar localStorage y no bloquear UI con spinner
  const msg = unrecoverableMessage(status, err)
  if (mounted) fail(msg)
}

function handlePollFailure(err: unknown, mounted: boolean, hooks: PollStatusHooks): void {
  if (!mounted) return
  // 401 durante polling de job: no mostrar alerta intrusiva, reintentar silenciosamente en segundo plano
  // (JWT extendido a 1440 min mitiga vencimiento durante procesamiento largo)
  const status = pollFailureStatus(err)
  const kind = classifyPollFailure(status)
  if (kind === 'silent-retry') {
    // Intentar refrescar token silenciosamente: re-leer desde localStorage (si fue renovado por otra pestaña/auth)
    // Mantener UI de progreso sin interrupción
    console.warn('[useJobPolling] 401 en polling job, reintentando sin mostrar error')
    hooks.retrySilently()
    // No setear error para evitar alerta roja bloqueante
    return
  }
  if (kind === 'unrecoverable') {
    handleUnrecoverablePollFailure(status, err, mounted, hooks.fail)
    return
  }
  hooks.fail(pollErrorMessage(err))
}

function rejectInvalidJobId(jobId: string, mounted: boolean, fail: (msg: string) => void): void {
  console.error('[useJobPolling] jobId inválido:', jobId)
  try { localStorage.removeItem('clipsai_active_job_id') } catch {}
  if (mounted) fail('Identificador de job inválido. Redirigiendo a subida...')
}

async function fetchStatusOnce(
  trimmed: string,
  mounted: boolean,
  hooks: PollStatusHooks,
): Promise<JobResponse | undefined> {
  try {
    const res = await jobService.getJobStatus(trimmed)
    if (!mounted) return undefined
    hooks.onJob(res)
    hooks.clearError()
    const st = res.status.toUpperCase()
    if (st === 'COMPLETED') hooks.onStatus('completed')
    else if (st === 'FAILED') hooks.onStatus('failed')
    else hooks.onStatus('polling')
    return res
  } catch (err) {
    handlePollFailure(err, mounted, hooks)
    return undefined
  }
}

export function useJobPolling(jobId: string | undefined): UseJobPollingResult {
  const [job, setJob] = useState<JobResponse | null>(null)
  const [pollingStatus, setPollingStatus] = useState<PollingStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<number | null>(null)
  const mountedRef = useRef(true)

  const fetchOnce = useCallback(async (): Promise<JobResponse | undefined> => {
    if (!jobId) return undefined
    // Validación de jobId nulo/vacío/inválido antes de pedir al backend
    const trimmed = jobId.trim()
    if (isInvalidJobId(trimmed)) {
      rejectInvalidJobId(jobId, mountedRef.current, (msg) => { setError(msg); setPollingStatus('error') })
      return undefined
    }
    return fetchStatusOnce(trimmed, mountedRef.current, {
      onJob: setJob,
      onStatus: setPollingStatus,
      fail: (msg) => { setError(msg); setPollingStatus('error') },
      clearError: () => setError(null),
      retrySilently: () => setPollingStatus('polling'),
    })
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
