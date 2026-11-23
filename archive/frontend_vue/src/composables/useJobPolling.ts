import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { jobService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { JobResponse } from '@/types/api'

export type PollingStatus = 'idle' | 'polling' | 'completed' | 'failed' | 'error'

function isTerminal(status: string): boolean {
  const s = status.toUpperCase()
  return s === 'COMPLETED' || s === 'FAILED'
}

function isInvalidJobId(trimmed: string): boolean {
  return !trimmed || trimmed === 'null' || trimmed === 'undefined'
}

function pollFailureStatus(err: unknown): number {
  return err instanceof ApiError ? (err as ApiError).status : 0
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

type ErrorRef = Ref<string | null>
type StatusRef = Ref<PollingStatus>

function handleUnrecoverablePollFailure(status: number, err: unknown, error: ErrorRef): void {
  // 404/500: job no existe o error servidor → limpiar localStorage y no bloquear UI con spinner
  error.value = unrecoverableMessage(status, err)
}

function handlePollFailure(err: unknown, error: ErrorRef, pollingStatus: StatusRef): void {
  const status = pollFailureStatus(err)
  const kind = classifyPollFailure(status)
  if (kind === 'silent-retry') {
    // 401 en polling: reintento silencioso sin alerta roja (JWT 1440 min evita vencimiento)
    console.warn('[useJobPolling] 401 en polling job Vue, reintentando sin mostrar error')
    pollingStatus.value = 'polling'
    // No setear error para no bloquear UI con alerta intrusiva
    return
  }
  if (kind === 'unrecoverable') {
    handleUnrecoverablePollFailure(status, err, error)
  } else {
    error.value = pollErrorMessage(err)
  }
  pollingStatus.value = 'error'
}

function rejectInvalidJobId(id: string, error: ErrorRef, pollingStatus: StatusRef): void {
  console.error('[useJobPolling] jobId inválido:', id)
  try { localStorage.removeItem('clipsai_active_job_id') } catch {}
  error.value = 'Identificador de job inválido. Redirigiendo a subida...'
  pollingStatus.value = 'error'
}

async function fetchStatusOnce(
  trimmed: string,
  job: Ref<JobResponse | null>,
  error: ErrorRef,
  pollingStatus: StatusRef,
): Promise<JobResponse | undefined> {
  try {
    const res = await jobService.getJobStatus(trimmed)
    job.value = res
    error.value = null
    const st = res.status.toUpperCase()
    if (st === 'COMPLETED') pollingStatus.value = 'completed'
    else if (st === 'FAILED') pollingStatus.value = 'failed'
    else pollingStatus.value = 'polling'
    return res
  } catch (err) {
    handlePollFailure(err, error, pollingStatus)
    return undefined
  }
}

export function useJobPolling(jobId: () => string | undefined) {
  const job = ref<JobResponse | null>(null)
  const pollingStatus = ref<PollingStatus>('idle')
  const error = ref<string | null>(null)
  let timer: number | null = null

  async function fetchOnce() {
    const id = jobId()
    if (!id) return
    const trimmed = (id ?? '').trim()
    if (isInvalidJobId(trimmed)) {
      rejectInvalidJobId(id, error, pollingStatus)
      return undefined
    }
    return fetchStatusOnce(trimmed, job, error, pollingStatus)
  }

  function start() {
    stop()
    const id = jobId()
    if (!id) {
      pollingStatus.value = 'idle'
      return
    }
    pollingStatus.value = 'polling'
    void fetchOnce()
    timer = window.setInterval(() => {
      void (async () => {
        const res = await fetchOnce()
        if (res && isTerminal(res.status) && timer !== null) {
          clearInterval(timer)
          timer = null
        }
      })()
    }, 2000)
  }

  function stop() {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  watch(() => job.value?.status, (s) => {
    if (s && isTerminal(s) && timer !== null) {
      clearInterval(timer)
      timer = null
    }
  })

  onMounted(start)
  onUnmounted(stop)

  watch(() => jobId(), () => {
    job.value = null
    error.value = null
    start()
  })

  return { job, pollingStatus, error, refresh: fetchOnce, start, stop }
}
