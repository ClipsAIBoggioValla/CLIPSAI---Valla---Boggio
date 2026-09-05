<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { jobService, videoService } from '@/api/services'
import { ApiError } from '@/types/api'

const router = useRouter()
const videoFile = ref<File | null>(null)
const transcriptFile = ref<File | null>(null)
type UploadState = 'idle' | 'uploading' | 'creating_job'
const status = ref<UploadState>('idle')
const error = ref<string | null>(null)

function onVideoChange(e: Event) {
  const t = e.target as HTMLInputElement
  videoFile.value = t.files?.[0] ?? null
}
function onTranscriptChange(e: Event) {
  const t = e.target as HTMLInputElement
  transcriptFile.value = t.files?.[0] ?? null
}

async function handleSubmit() {
  if (!videoFile.value || !transcriptFile.value) {
    error.value = 'Selecciona ambos archivos: video y transcripción.'
    return
  }
  error.value = null
  try {
    status.value = 'uploading'
    const video = await videoService.upload(videoFile.value, transcriptFile.value)
    status.value = 'creating_job'
    const job = await jobService.createJob(video.id)
    const jobId = job.job_id ?? job.id
    router.push(`/jobs/${jobId}`)
  } catch (err: unknown) {
    status.value = 'idle'
    error.value = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error inesperado durante la subida.'
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
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
          <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" class="hidden" :disabled="status !== 'idle'" @change="onVideoChange" />
        </label>
      </div>

      <div>
        <label class="form-label-custom">Archivo de Transcripción <span class="text-[#B4F105]">*</span></label>
        <label :class="['dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer', transcriptFile ? 'has-file' : '']">
          <span class="dropzone-icon-neon mb-3"><i class="bi bi-file-earmark-text" /></span>
          <span class="text-sm font-bold" style="color: #F1F5F9">{{ transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción' }}</span>
          <span class="text-xs mt-1" style="color: #94A3B8">.txt, .srt (UTF-8)</span>
          <span v-if="transcriptFile" class="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]"><i class="bi bi-check-circle-fill" /> {{ (transcriptFile.size / 1024).toFixed(0) }} KB</span>
          <input type="file" accept=".txt,.srt,text/plain" class="hidden" :disabled="status !== 'idle'" @change="onTranscriptChange" />
        </label>
      </div>

      <button type="submit" :disabled="status !== 'idle' || !videoFile || !transcriptFile" class="btn-custom btn-custom-primary w-full justify-center btn-custom-lg shadow-[0_0_28px_rgba(180,241,5,0.35)]">
        <span v-if="status !== 'idle'" class="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" />
        <i v-else class="bi bi-lightning-charge-fill" />
        {{ status === 'uploading' ? 'Subiendo archivos...' : status === 'creating_job' ? 'Iniciando procesamiento...' : 'Subir y procesar' }}
      </button>

      <div v-if="status !== 'idle'" class="space-y-2">
        <div class="progress"><div class="progress-bar w-full animate-pulse" style="height: 10px; border-radius: 50rem" /></div>
        <p class="text-xs text-center" style="color: #94A3B8"><i class="bi bi-shield-lock mr-1" /> No cierres esta ventana</p>
      </div>
    </form>
  </div>
</template>
