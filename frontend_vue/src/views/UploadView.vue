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
  <div class="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
    <div class="max-w-3xl mx-auto px-4 py-8 sm:py-12">
      <div class="mb-8">
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">Subir video</h1>
        <p class="text-slate-600 mt-2">Sube tu video y su transcripción para generar clips automáticamente.</p>
      </div>

      <div v-if="error" role="alert" class="mb-6 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 flex gap-3">
        <span class="text-red-400">⚠</span>
        <p class="text-sm text-red-300">{{ error }}</p>
      </div>

      <form class="bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl p-6 sm:p-8 space-y-6" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-slate-900 dark:text-white font-bold mb-2">Archivo de Video <span class="text-brand-500">*</span></label>
          <label class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 bg-slate-50 dark:bg-slate-800/50 border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 transition p-6 sm:p-8 cursor-pointer">
            <span class="text-3xl mb-2">🎬</span>
            <span class="text-slate-800 dark:text-slate-200 font-semibold">{{ videoFile ? videoFile.name : 'Arrastra o selecciona tu video' }}</span>
            <span class="text-slate-600 dark:text-slate-400 font-medium mt-1">.mp4, .mov (máx. 500MB)</span>
            <span v-if="videoFile" class="text-xs text-brand-500 mt-2">{{ (videoFile.size / 1024 / 1024).toFixed(1) }} MB</span>
            <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" class="hidden" :disabled="status !== 'idle'" @change="onVideoChange" />
          </label>
        </div>

        <div>
          <label class="block text-slate-900 dark:text-white font-bold mb-2">Archivo de Transcripción <span class="text-brand-500">*</span></label>
          <label class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 bg-slate-50 dark:bg-slate-800/50 border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 transition p-6 sm:p-8 cursor-pointer">
            <span class="text-3xl mb-2">📄</span>
            <span class="text-slate-800 dark:text-slate-200 font-semibold">{{ transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción' }}</span>
            <span class="text-slate-600 dark:text-slate-400 font-medium mt-1">.txt (UTF-8)</span>
            <span v-if="transcriptFile" class="text-xs text-brand-500 mt-2">{{ (transcriptFile.size / 1024).toFixed(0) }} KB</span>
            <input type="file" accept=".txt,.srt,text/plain" class="hidden" :disabled="status !== 'idle'" @change="onTranscriptChange" />
          </label>
        </div>

        <button type="submit" :disabled="status !== 'idle' || !videoFile || !transcriptFile" class="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold py-3.5 px-4 transition">
          <span v-if="status !== 'idle'" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          {{ status === 'uploading' ? 'Subiendo archivos...' : status === 'creating_job' ? 'Iniciando procesamiento...' : 'Subir y procesar' }}
        </button>

        <div v-if="status !== 'idle'" class="space-y-2">
          <div class="h-2 bg-white dark:bg-slate-800 rounded-full overflow-hidden"><div class="h-full w-full bg-gradient-to-r from-violet-600 to-indigo-600 animate-pulse rounded-full" /></div>
          <p class="text-xs text-center text-slate-600">No cierres esta ventana</p>
        </div>
      </form>
    </div>
  </div>
</template>
