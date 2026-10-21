<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { jobService, videoService } from '@/api/services'
import { ApiError } from '@/types/api'

const router = useRouter()
const videoFile = ref<File | null>(null)
const transcriptFile = ref<File | null>(null)
type UploadState = 'idle' | 'uploading' | 'creating_job'
const status = ref<UploadState>('idle')
type DirectUploadState = 'idle' | 'uploading' | 'processing' | 'success' | 'error'
const directUploadState = ref<DirectUploadState>('idle')
const directUploadError = ref<string | null>(null)
const directUploadKey = ref<string | null>(null)
const directUploadResult = ref<import('@/types/api').RunPodProcessResponse | null>(null)
const error = ref<string | null>(null)
const activeJobId = ref<string | null>(null)
const isDirectUploadBusy = computed(() => directUploadState.value === 'uploading' || directUploadState.value === 'processing')
type SampleState = 'idle' | 'loading' | 'error'
const sampleState = ref<SampleState>('idle')
const sampleError = ref<string | null>(null)
const isSampleBusy = computed(() => sampleState.value === 'loading')

onMounted(() => {
  try {
    const id = localStorage.getItem('clipsai_active_job_id')
    if (id) activeJobId.value = id
  } catch {}
})

function onVideoChange(e: Event) {
  const t = e.target as HTMLInputElement
  videoFile.value = t.files?.[0] ?? null
  directUploadState.value = 'idle'
  directUploadError.value = null
  directUploadKey.value = null
  directUploadResult.value = null
}
function onTranscriptChange(e: Event) {
  const t = e.target as HTMLInputElement
  transcriptFile.value = t.files?.[0] ?? null
}

async function handleFileUpload(file: File) {
  directUploadState.value = 'uploading'
  directUploadError.value = null
  directUploadKey.value = null
  directUploadResult.value = null
  try {
    const result = await videoService.uploadDirectToStorage(file)
    directUploadKey.value = result.file_key
    directUploadState.value = 'processing'
    directUploadResult.value = await videoService.processDirectUpload(result.file_key)
    directUploadState.value = 'success'
  } catch (err: unknown) {
    directUploadError.value = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error inesperado durante la subida directa.'
    directUploadState.value = 'error'
  }
}

/** Issue 34: iniciar job con video de muestra sin subir archivo. */
async function handleSampleJob() {
  sampleState.value = 'loading'
  sampleError.value = null
  try {
    const job = await videoService.createSampleJob()
    const jobId = job.job_id ?? job.id
    try {
      localStorage.setItem('clipsai_active_job_id', jobId)
    } catch {}
    router.push(`/jobs/${jobId}`)
  } catch (err: unknown) {
    sampleError.value = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error inesperado al crear el job de muestra.'
    sampleState.value = 'error'
  }
}

async function handleSubmit() {
  if (!videoFile.value) {
    error.value = 'Selecciona el archivo de video.'
    return
  }
  error.value = null
  try {
    status.value = 'uploading'
    const video = await videoService.upload(videoFile.value, transcriptFile.value ?? null)
    status.value = 'creating_job'
    const job = await jobService.createJob(video.id)
    const jobId = job.job_id ?? job.id
    try {
      localStorage.setItem('clipsai_active_job_id', jobId)
    } catch {}
    router.push(`/jobs/${jobId}`)
  } catch (err: unknown) {
    status.value = 'idle'
    error.value = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error inesperado durante la subida.'
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div v-if="activeJobId" class="rounded-xl border border-[rgba(180,241,5,0.22)] bg-[rgba(180,241,5,0.08)] px-4 py-3 flex items-center justify-between gap-3 mb-6">
      <span class="text-sm font-bold text-[#B4F105] flex items-center gap-2"><span class="h-2 w-2 rounded-full bg-[#B4F105] animate-pulse" /> Procesamiento activo</span>
      <RouterLink :to="`/jobs/${activeJobId}`" class="btn-custom btn-custom-primary btn-custom-sm">Ver progreso {{ activeJobId.slice(0,8) }} →</RouterLink>
    </div>
    <div class="page-header" style="margin-bottom: 2rem">
      <div>
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]"><i class="bi bi-cloud-arrow-up" style="font-size: 1.15rem" /></span>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]"><i class="bi bi-stars" /> Nuevo</span>
        </div>
        <h1 class="page-title" style="margin-bottom: 0; font-size: 2.25rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; color: #F1F5F9">Subir video</h1>
        <p class="page-subtitle" style="margin-bottom: 0; margin-top: 0.7rem; font-size: 0.92rem; font-weight: 500; color: #94A3B8; line-height: 1.6; max-width: 640px">Sube tu video y su transcripción para generar clips automáticamente con IA.</p>
      </div>
    </div>

    <div v-if="error" role="alert" class="alert-custom alert-custom-danger">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
    </div>

    <form class="card-spark space-y-6" @submit.prevent="handleSubmit">
      <div>
        <label class="form-label-custom">Archivo de Video <span class="text-[#B4F105]">*</span></label>
        <label :class="['dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer', videoFile ? 'has-file' : '']">
          <span class="dropzone-icon-neon mb-3"><i class="bi bi-camera-video" /></span>
          <span class="text-sm font-bold" style="color: #F1F5F9">{{ videoFile ? videoFile.name : 'Arrastra o selecciona tu video' }}</span>
          <span class="text-xs mt-1" style="color: #94A3B8">.mp4, .mov, .avi (máx. 500MB)</span>
          <span v-if="videoFile" class="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]"><i class="bi bi-check-circle-fill" /> {{ (videoFile.size / 1024 / 1024).toFixed(1) }} MB</span>
          <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" class="hidden" :disabled="status !== 'idle' || isDirectUploadBusy || isSampleBusy" @change="onVideoChange" />
        </label>
        <!-- Issue 34: botón para probar con video de muestra -->
        <div class="mt-3">
          <button
            type="button"
            :disabled="status !== 'idle' || isDirectUploadBusy || isSampleBusy"
            class="btn-custom btn-custom-light w-full justify-center disabled:opacity-50"
            @click="handleSampleJob"
          >
            <span v-if="sampleState === 'loading'" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
            <i v-else class="bi bi-play-circle" />
            {{ sampleState === 'loading' ? 'Preparando video de muestra...' : 'Probar con video de muestra' }}
          </button>
          <p v-if="sampleState === 'error' && sampleError" role="alert" class="text-xs text-red-400 mt-2">{{ sampleError }}</p>
          <p class="text-xs text-[#94A3B8] mt-2 text-center">Usa un clip liviano de ejemplo para evaluar el flujo completo sin subir archivos pesados.</p>
        </div>
      </div>

      <div>
        <label class="form-label-custom">Archivo de Transcripción <span class="text-[#94A3B8] font-normal">(opcional)</span></label>
        <label :class="['dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer', transcriptFile ? 'has-file' : '']">
          <span class="dropzone-icon-neon mb-3"><i class="bi bi-file-earmark-text" /></span>
          <span class="text-sm font-bold" style="color: #F1F5F9">{{ transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción' }}</span>
          <span class="text-xs mt-1" style="color: #94A3B8">.txt, .srt (UTF-8)</span>
          <span v-if="transcriptFile" class="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]"><i class="bi bi-check-circle-fill" /> {{ (transcriptFile.size / 1024).toFixed(0) }} KB</span>
          <input type="file" accept=".txt,.srt,text/plain" class="hidden" :disabled="status !== 'idle' || isDirectUploadBusy" @change="onTranscriptChange" />
        </label>
      </div>

      <div class="rounded-xl border border-white/10 bg-[#0B0F17] p-4 space-y-3">
        <div>
          <p class="text-sm font-bold text-[#F1F5F9]">Subida directa a Cloudflare R2</p>
          <p class="text-xs mt-1 text-[#94A3B8]">Sube el video a R2 y envía su URL prefirmada al worker de RunPod.</p>
        </div>
        <button
          type="button"
          :disabled="!videoFile || isDirectUploadBusy || status !== 'idle'"
          class="btn-custom btn-custom-light w-full justify-center disabled:opacity-50"
          @click="videoFile && handleFileUpload(videoFile)"
        >
          <span v-if="isDirectUploadBusy" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
          <i v-else-if="directUploadState === 'success'" class="bi bi-check-circle-fill text-emerald-400" />
          <i v-else class="bi bi-cloud-arrow-up" />
          {{ directUploadState === 'uploading' ? 'Subiendo a R2...' : directUploadState === 'processing' ? 'Procesando con RunPod...' : directUploadState === 'success' ? 'Procesamiento completado' : 'Subir video a R2 y procesar' }}
        </button>
        <div v-if="isDirectUploadBusy" role="status" class="space-y-2">
          <div class="progress"><div class="progress-bar w-full animate-pulse" style="height: 8px; border-radius: 50rem" /></div>
          <p class="text-xs text-center text-[#94A3B8]">{{ directUploadState === 'uploading' ? 'Transfiriendo archivo directamente al storage...' : 'RunPod está analizando el video y buscando clips...' }}</p>
        </div>
        <div v-if="directUploadState === 'success' && directUploadKey" role="status" class="space-y-2">
          <p class="text-xs text-emerald-400 break-all">Archivo procesado. Clave R2: {{ directUploadKey }}</p>
          <p class="text-xs text-[#CBD5E1]">{{ directUploadResult?.clip_count ?? directUploadResult?.clips?.length ?? 0 }} clips devueltos · motor {{ directUploadResult?.engine ?? 'ClipsAI' }}</p>
          <ul v-if="directUploadResult?.clips?.length" class="space-y-2">
            <li v-for="(clip, index) in directUploadResult.clips" :key="`${clip.start_time ?? clip.inicio ?? index}-${index}`" class="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
              <p class="text-sm font-semibold text-[#F1F5F9]">{{ clip.title ?? clip.titulo_sugerido ?? clip.titulo ?? `Clip ${index + 1}` }}</p>
              <p class="text-xs text-[#94A3B8]">{{ clip.start_time ?? clip.inicio ?? '—' }} – {{ clip.end_time ?? clip.fin ?? '—' }}<span v-if="clip.score !== undefined"> · Score {{ clip.score }}</span></p>
            </li>
          </ul>
          <p v-else class="text-xs text-[#94A3B8]">El worker no devolvió clips para este video.</p>
        </div>
        <p v-if="directUploadState === 'error' && directUploadError" role="alert" class="text-xs text-red-400">{{ directUploadError }}</p>
      </div>

      <button type="submit" :disabled="status !== 'idle' || isDirectUploadBusy || !videoFile" class="btn-custom btn-custom-primary w-full justify-center btn-custom-lg shadow-[0_0_28px_rgba(180,241,5,0.35)]">
        <span v-if="status !== 'idle'" class="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" />
        <i v-else class="bi bi-lightning-charge-fill" />
        {{ status === 'uploading' ? 'Subiendo archivos...' : status === 'creating_job' ? 'Iniciando procesamiento...' : 'Subir y procesar' }}
      </button>

      <div v-if="status !== 'idle'" class="space-y-2">
        <div class="progress"><div class="progress-bar w-full animate-pulse" style="height: 10px; border-radius: 50rem" /></div>
        <p class="text-xs text-center" style="color: #94A3B8"><i class="bi bi-shield-lock mr-1" />No cierres esta ventana</p>
      </div>
    </form>
  </div>
</template>
