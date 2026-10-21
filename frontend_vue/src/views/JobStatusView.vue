<template>
  <div class="max-w-2xl mx-auto">
    <RouterLink to="/upload" class="btn-custom btn-custom-light mb-6"><i class="bi bi-arrow-left" /> Volver a subir</RouterLink>

    <div class="card-spark">
      <h1 class="card-title">Estado del procesamiento</h1>
      <p class="text-sm font-mono break-all" style="color: var(--text-muted-green)">Job ID: {{ jobId }}</p>

      <div v-if="error" role="alert" class="alert-custom alert-custom-danger mt-6">
        <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
        <div class="alert-custom-content">{{ error }}</div>
      </div>

      <div v-if="isInitialLoading || (!job && pollingStatus === 'polling' && !error)" class="mt-8 flex flex-col items-center gap-3 py-8">
        <span class="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
        <p class="text-sm" style="color: var(--text-muted-green)">{{ isInitialLoading ? 'Cargando...' : 'Consultando estado...' }}</p>
      </div>
      <div v-else-if="!isInitialLoading && !job && pollingStatus !== 'polling' && !error" class="mt-8 flex flex-col items-center gap-3 py-8">
        <p class="text-sm" style="color: var(--text-muted-green)">No se pudo cargar el job. Es posible que haya expirado.</p>
        <RouterLink to="/upload" class="btn-custom btn-custom-primary">Ir a subir video</RouterLink>
      </div>

      <div v-if="job" class="mt-6 space-y-6">
        <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-4 border" style="background-color: var(--bs-body-bg); border-color: var(--border-light)">
          <span class="text-sm font-bold" style="color: var(--text-muted-green)">Estado</span>
          <StatusBadge :status="job.status" />
        </div>

        <div v-if="job.status === 'PROCESSING' || job.status === 'PENDING'" class="space-y-2 rounded-xl px-4 py-4 border" style="background-color: var(--bs-body-bg); border-color: var(--border-light)">
          <div class="flex justify-between items-center text-xs font-bold">
            <span style="color: var(--text-muted-green)">{{ job.status === 'PENDING' ? 'En cola...' : `Procesando... ${job.progress ?? 0}%` }}</span>
            <span style="color: var(--text-main)">{{ job.progress ?? 0 }}%</span>
          </div>
          <div class="w-full rounded-full h-2.5 overflow-hidden border" style="background-color: rgba(0,0,0,0.2); border-color: var(--border-light)">
            <div class="h-2.5 rounded-full transition-all duration-500 ease-out" :style="{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%`, backgroundColor: '#B4F105', boxShadow: '0 0 8px rgba(180,241,5,0.4)' }" />
          </div>
          <p class="text-[11px] text-center font-medium" style="color: var(--text-muted-green)">
            <span v-if="(job.progress ?? 0) === 10">Extrayendo y transcribiendo audio con Whisper...</span>
            <span v-else-if="(job.progress ?? 0) === 35">Transcripción (Whisper) completada...</span>
            <span v-else-if="(job.progress ?? 0) === 65">Análisis de hooks (Claude) completado...</span>
            <span v-else-if="(job.progress ?? 0) >= 70 && (job.progress ?? 0) < 90">Renderizando clips...</span>
            <span v-else-if="(job.progress ?? 0) >= 90 && (job.progress ?? 0) < 100">Finalizando renderizado...</span>
            <span v-else-if="(job.progress ?? 0) === 0">Esperando en cola...</span>
            <span v-else-if="(job.progress ?? 0) > 35 && (job.progress ?? 0) < 65">Analizando contenido viral...</span>
          </p>
        </div>

        <div v-if="job.status === 'PENDING'" class="alert-custom alert-custom-warning">
          <i class="bi bi-hourglass-split alert-custom-icon" />
          <div class="alert-custom-content"><strong>En cola...</strong> Tu video está esperando a ser procesado. Esto se actualiza solo.</div>
        </div>

        <div v-if="job.status === 'PROCESSING'" class="alert-custom alert-custom-info">
          <i class="bi bi-arrow-repeat alert-custom-icon" />
          <div class="alert-custom-content"><strong>Procesando video y generando clips...</strong> Puede tardar unos minutos. La página se actualiza automáticamente.</div>
        </div>

        <CompletedClips v-if="job.status === 'COMPLETED'" :job="job" :real-clips="realClips" :clips-error="clipsError" :job-id="jobId ?? ''" :api-base-url="API_BASE_URL" />

        <div v-if="job.status === 'FAILED'" role="alert" class="alert-custom alert-custom-danger flex-col items-start">
          <div class="flex gap-3 w-full">
            <i class="bi bi-x-circle-fill alert-custom-icon" />
            <div class="alert-custom-content"><strong>Error en el procesamiento</strong><p class="mt-1 break-words opacity-80">{{ job.error_message || 'El job falló sin mensaje detallado. Intenta subir el video nuevamente.' }}</p></div>
          </div>
          <RouterLink to="/upload" class="btn-custom btn-custom-light mt-3"><i class="bi bi-arrow-repeat" /> Intentar de nuevo</RouterLink>
        </div>

        <div class="pt-2 border-t grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs" style="border-color: var(--border-light); color: var(--text-muted-green)">
          <span>Creado: {{ new Date(job.created_at).toLocaleString() }}</span>
          <span>Actualizado: {{ new Date(job.updated_at).toLocaleString() }}</span>
        </div>
      </div>
    </div>

    <p class="text-center text-xs mt-6" style="color: var(--text-muted-green)">Se actualiza cada 2 segundos sin recargar la página</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useJobPolling } from '@/composables/useJobPolling'
import { clipService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { ClipListItem } from '@/types/api'
import StatusBadge from '@/components/job-status/StatusBadge.vue'
import CompletedClips from '@/components/job-status/CompletedClips.vue'
const route = useRoute()
const router = useRouter()
const jobId = computed(() => route.params.jobId as string | undefined)
const { job, pollingStatus, error } = useJobPolling(() => jobId.value)

const ACTIVE_JOB_KEY = 'clipsai_active_job_id'
const isInitialLoading = ref(true)
const realClips = ref<ClipListItem[] | null>(null)
const clipsError = ref<string | null>(null)
const RAW = (import.meta.env.VITE_API_URL as string | undefined ?? '').trim()
const API_BASE_URL = (RAW || 'http://localhost:8000').replace(/\/$/, '')

onMounted(() => {
  const safety = window.setTimeout(() => { isInitialLoading.value = false }, 5000)
  const doHydrate = async () => {
    try {
      const activeJobId = (() => { try { return localStorage.getItem(ACTIVE_JOB_KEY) } catch { return null } })() || jobId.value
      if (activeJobId) {
        if (!activeJobId.trim() || activeJobId === 'null' || activeJobId === 'undefined') throw new Error('jobId inválido')
        if (!jobId.value && activeJobId) router.replace(`/jobs/${activeJobId}`)
        else if (jobId.value) { try { localStorage.setItem(ACTIVE_JOB_KEY, jobId.value) } catch {} }
      }
    } catch (err) {
      console.error('Error al restaurar la sesión del job:', err)
      try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
    } finally {
      isInitialLoading.value = false
      window.clearTimeout(safety)
    }
  }
  doHydrate()
})

watch(() => jobId.value, (id) => {
  if (id) { try { localStorage.setItem(ACTIVE_JOB_KEY, id) } catch {} }
})

watch(() => [job.value, pollingStatus.value, error.value], () => {
  if (job.value || error.value || pollingStatus.value === 'completed' || pollingStatus.value === 'failed' || pollingStatus.value === 'error') isInitialLoading.value = false
})

watch(() => error.value, (errMsg) => {
  if (errMsg && (errMsg.includes('no encontrado') || errMsg.includes('inválido') || errMsg.includes('expirado') || errMsg.includes('Job no encontrado'))) {
    try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
    window.setTimeout(() => router.replace('/upload'), 1200)
  }
})

watch(() => job.value?.status, async (s) => {
  if (s?.toUpperCase() === 'COMPLETED' && jobId.value) {
    try {
      const res = await clipService.getClips({ job_id: jobId.value, limit: 50 })
      const sorted = [...res.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      realClips.value = sorted
    } catch (e: unknown) {
      clipsError.value = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error al cargar clips físicos'
    }
  } else {
    realClips.value = null
  }
}, { immediate: true })
</script>
