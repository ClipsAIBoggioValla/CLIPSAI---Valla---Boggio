<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useJobPolling } from '@/composables/useJobPolling'
import { clipService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { ClipListItem } from '@/types/api'

const route = useRoute()
const router = useRouter()
const jobId = computed(() => route.params.jobId as string | undefined)
const { job, pollingStatus, error } = useJobPolling(() => jobId.value)

const ACTIVE_JOB_KEY = 'clipsai_active_job_id'
const isInitialLoading = ref(true)

onMounted(() => {
  const safety = window.setTimeout(() => { isInitialLoading.value = false }, 5000)
  const doHydrate = async () => {
    try {
      const activeJobId = (() => { try { return localStorage.getItem(ACTIVE_JOB_KEY) } catch { return null } })() || jobId.value
      if (activeJobId) {
        if (!activeJobId.trim() || activeJobId === 'null' || activeJobId === 'undefined') {
          throw new Error('jobId inválido')
        }
        if (!jobId.value && activeJobId) {
          router.replace(`/jobs/${activeJobId}`)
        } else if (jobId.value) {
          try { localStorage.setItem(ACTIVE_JOB_KEY, jobId.value) } catch {}
        }
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

watch(
  () => jobId.value,
  (id) => {
    if (id) {
      try {
        localStorage.setItem(ACTIVE_JOB_KEY, id)
      } catch {}
    }
  },
)

watch(
  () => error.value,
  (errMsg) => {
    if (errMsg && (errMsg.includes('no encontrado') || errMsg.includes('inválido') || errMsg.includes('expirado') || errMsg.includes('Job no encontrado'))) {
      try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      window.setTimeout(() => router.replace('/upload'), 1200)
    }
  },
)

watch(
  () => [job.value, pollingStatus.value, error.value],
  () => {
    if (job.value || error.value || pollingStatus.value === 'completed' || pollingStatus.value === 'failed' || pollingStatus.value === 'error') {
      isInitialLoading.value = false
    }
  },
)
const clips = computed(() => job.value?.result_metadata?.clips ?? [])
const realClips = ref<ClipListItem[] | null>(null)
const clipsError = ref<string | null>(null)
const RAW = (import.meta.env.VITE_API_URL as string | undefined ?? '').trim()
const API_BASE_URL = (RAW || 'http://localhost:8000').replace(/\/$/, '')
function getVideoSrc(clip: ClipListItem): string {
  const bust = clip.updated_at ? `?t=${new Date(clip.updated_at).getTime()}` : `?t=${Date.now()}`
  const base = clip.stream_url
    ? (clip.stream_url.startsWith('http') ? clip.stream_url : `${API_BASE_URL}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}`)
    : `${API_BASE_URL}/clips/${clip.id}/descarga`
  return `${base}${base.includes('?') ? '&' : '?'}t=${bust.slice(1)}`
}
watch(
  () => job.value?.status,
  async (s) => {
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
  },
  { immediate: true }
)
</script>

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
          <span v-if="job.status === 'PENDING'" class="badge-table pending"><span class="h-2 w-2 rounded-full bg-[var(--sys-orange)] animate-pulse" /> En cola...</span>
          <span v-else-if="job.status === 'PROCESSING'" class="badge-table" style="background-color: rgba(59,130,246,0.1); color: #3b82f6"><span class="h-4 w-4 animate-spin rounded-full border-2 border-[rgba(59,130,246,0.3)] border-t-[var(--sys-orange)]" /> Procesando...</span>
          <span v-else-if="job.status === 'COMPLETED'" class="badge-table success">✓ ¡Completado!</span>
          <span v-else-if="job.status === 'FAILED'" class="badge-table failed">✕ Falló</span>
          <span v-else class="badge-table pending">{{ job.status }}</span>
        </div>

        <!-- Barra de progreso en tiempo real (0-100%) mientras el job está activo -->
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

          <div v-if="job.status === 'COMPLETED'" class="space-y-4">
            <div class="alert-custom alert-custom-success">
            <i class="bi bi-check-circle-fill alert-custom-icon" />
            <div class="alert-custom-content"><strong>¡Procesamiento Completado!</strong> {{ realClips ? `${realClips.length} clip${realClips.length !== 1 ? 's' : ''} generado${realClips.length !== 1 ? 's' : ''} — archivos .mp4 físicos listos` : `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}` }}<span v-if="job.result_metadata?.engine" class="ml-2 text-xs" style="color: var(--text-muted-green)">· motor: {{ job.result_metadata.engine }}</span></div>
          </div>

          <div v-if="realClips && realClips.length > 0" class="grid gap-3 sm:gap-4">
            <div v-for="clip in realClips" :key="clip.id" class="card-spark flex flex-col gap-3" style="padding: 1.25rem">
              <div class="flex items-start justify-between gap-3">
                <h3 class="text-sm font-bold leading-snug line-clamp-2" style="color: var(--text-main)">{{ clip.title || 'Clip sin título' }}</h3>
                <span class="badge-table success">Viral Score: {{ (clip.score ?? 0).toFixed(1) }}/100</span>
              </div>
              <p class="text-xs font-mono rounded-lg px-3 py-2 border flex items-center gap-2" style="color: var(--text-muted-green); background-color: var(--bs-body-bg); border-color: var(--border-light)"><i class="bi bi-clock" /> {{ clip.start_time.toFixed(1) }}s — {{ clip.end_time.toFixed(1) }}s · {{ String(Math.floor((clip.duration ?? clip.end_time-clip.start_time)/60)).padStart(2,'0') }}:{{ String(Math.floor((clip.duration ?? clip.end_time-clip.start_time)%60)).padStart(2,'0') }}</p>
              <div class="flex items-center gap-2 text-[11px] font-bold">
                <span :class="`px-2 py-1 rounded-full border ${clip.has_ass ? 'bg-[#B4F105]/15 text-[#B4F105] border-[#B4F105]/30' : 'bg-white/5 text-[#94A3B8] border-white/10'}`">ASS {{ clip.has_ass ? '✓' : '✗' }}</span>
                <span :class="`px-2 py-1 rounded-full border ${clip.has_hook ? 'bg-[#B4F105]/15 text-[#B4F105] border-[#B4F105]/30' : 'bg-white/5 text-[#94A3B8] border-white/10'}`">Hook {{ clip.has_hook ? '✓' : '✗' }}</span>
                <span class="ml-auto text-[11px] font-mono px-2 py-1 rounded-full bg-[#0B0F17] border border-white/10 text-[#CBD5E1]">ready</span>
              </div>
              <div class="rounded-xl overflow-hidden border border-white/10 bg-black flex justify-center p-2">
                <video controls playsinline :src="getVideoSrc(clip)" class="rounded-lg shadow-xl" style="aspect-ratio: 9/16; max-height: 50vh; width: auto; max-width: 240px; object-fit: contain; background: black" />
              </div>
              <p class="text-xs font-mono break-all px-2 py-1 rounded bg-[#0B0F17] border border-white/5" style="color: #64748B">{{ clip.file_path || clip.stream_url }}</p>
              <div class="grid grid-cols-2 gap-2">
                <a :href="getVideoSrc(clip)" :download="`${clip.title || clip.id}.mp4`" class="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1"><i class="bi bi-download" /> Descargar MP4</a>
                <RouterLink :to="`/clips?job_id=${jobId}`" class="btn-custom btn-custom-primary !py-2 text-xs font-bold flex items-center justify-center gap-1">Ver en galería <i class="bi bi-arrow-right" /></RouterLink>
              </div>
            </div>
          </div>
          <div v-else-if="clipsError" role="alert" class="alert-custom alert-custom-danger"><i class="bi bi-exclamation-triangle-fill alert-custom-icon" /><div class="alert-custom-content">{{ clipsError }}</div></div>
          <div v-else-if="clips.length > 0" class="grid gap-3 sm:gap-4">
            <div v-for="(clip, idx) in clips" :key="`${clip.titulo}-${idx}`" class="card-spark flex flex-col gap-3" style="padding: 1.25rem; opacity: 0.85">
              <div class="flex items-center gap-2 text-xs text-amber-400"><i class="bi bi-hourglass-split" /> Cargando clips físicos…</div>
              <h3 class="text-sm font-bold" style="color: var(--text-main)">{{ clip.titulo }}</h3>
              <p class="text-xs font-mono px-3 py-2 border" style="color: var(--text-muted-green); background-color: var(--bs-body-bg); border-color: var(--border-light)">Inicio: {{ clip.inicio }} - Fin: {{ clip.fin }}</p>
            </div>
          </div>
          <RouterLink v-if="(!realClips || realClips.length===0) && clips.length===0" :to="`/clips?job_id=${job.job_id ?? job.id}`" class="btn-custom btn-custom-primary w-full justify-center">Ver clips generados <i class="bi bi-arrow-right" /></RouterLink>
        </div>

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
