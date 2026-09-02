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
  <div class="min-h-screen bg-gray-950 text-white">
    <div class="max-w-3xl mx-auto px-4 py-8 sm:py-12">
      <div class="mb-8">
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">Subir video</h1>
        <p class="text-gray-400 mt-2">Sube tu video y su transcripción para generar clips automáticamente.</p>
      </div>

      <div v-if="error" role="alert" class="mb-6 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 flex gap-3">
        <span class="text-red-400">⚠</span>
        <p class="text-sm text-red-300">{{ error }}</p>
      </div>

      <form class="bg-gray-900 border border-gray-800 rounded-2xl p-6 sm:p-8 space-y-6" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2">Archivo de Video <span class="text-violet-400">*</span></label>
          <label class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-700 bg-gray-800/50 hover:bg-gray-800 hover:border-gray-600 transition p-6 sm:p-8 cursor-pointer">
            <span class="text-3xl mb-2">🎬</span>
            <span class="text-sm font-medium text-gray-200">{{ videoFile ? videoFile.name : 'Arrastra o selecciona tu video' }}</span>
            <span class="text-xs text-gray-500 mt-1">.mp4, .mov (máx. 500MB)</span>
            <span v-if="videoFile" class="text-xs text-violet-400 mt-2">{{ (videoFile.size / 1024 / 1024).toFixed(1) }} MB</span>
            <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" class="hidden" :disabled="status !== 'idle'" @change="onVideoChange" />
          </label>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2">Archivo de Transcripción <span class="text-violet-400">*</span></label>
          <label class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-700 bg-gray-800/50 hover:bg-gray-800 hover:border-gray-600 transition p-6 sm:p-8 cursor-pointer">
            <span class="text-3xl mb-2">📄</span>
            <span class="text-sm font-medium text-gray-200">{{ transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción' }}</span>
            <span class="text-xs text-gray-500 mt-1">.txt (UTF-8)</span>
            <span v-if="transcriptFile" class="text-xs text-violet-400 mt-2">{{ (transcriptFile.size / 1024).toFixed(0) }} KB</span>
            <input type="file" accept=".txt,.srt,text/plain" class="hidden" :disabled="status !== 'idle'" @change="onTranscriptChange" />
          </label>
        </div>

        <button type="submit" :disabled="status !== 'idle' || !videoFile || !transcriptFile" class="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-medium py-3.5 px-4 transition">
          <span v-if="status !== 'idle'" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          {{ status === 'uploading' ? 'Subiendo archivos...' : status === 'creating_job' ? 'Iniciando procesamiento...' : 'Subir y procesar' }}
        </button>

        <div v-if="status !== 'idle'" class="space-y-2">
          <div class="h-2 bg-gray-800 rounded-full overflow-hidden"><div class="h-full w-full bg-violet-600 animate-pulse rounded-full" /></div>
          <p class="text-xs text-center text-gray-500">No cierres esta ventana</p>
        </div>
      </form>
    </div>
  </div>
</template>
