import { onMounted, onUnmounted, ref, watch } from 'vue'
import { jobService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { JobResponse } from '@/types/api'

export type PollingStatus = 'idle' | 'polling' | 'completed' | 'failed' | 'error'

function isTerminal(status: string): boolean {
  const s = status.toUpperCase()
  return s === 'COMPLETED' || s === 'FAILED'
}

export function useJobPolling(jobId: () => string | undefined) {
  const job = ref<JobResponse | null>(null)
  const pollingStatus = ref<PollingStatus>('idle')
  const error = ref<string | null>(null)
  let timer: number | null = null

  async function fetchOnce() {
    const id = jobId()
    if (!id) return
    try {
      const res = await jobService.getJobStatus(id)
      job.value = res
      error.value = null
      const st = res.status.toUpperCase()
      if (st === 'COMPLETED') pollingStatus.value = 'completed'
      else if (st === 'FAILED') pollingStatus.value = 'failed'
      else pollingStatus.value = 'polling'
      return res
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error al consultar el job'
      error.value = msg
      pollingStatus.value = 'error'
      return undefined
    }
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
