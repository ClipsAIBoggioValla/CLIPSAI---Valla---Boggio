<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useJobPolling } from '@/composables/useJobPolling'

const route = useRoute()
const jobId = computed(() => route.params.jobId as string | undefined)
const { job, pollingStatus, error } = useJobPolling(() => jobId.value)
const clips = computed(() => job.value?.result_metadata?.clips ?? [])
</script>

<template>
  <div class="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
    <div class="max-w-2xl mx-auto px-4 py-8 sm:py-12">
      <RouterLink to="/upload" class="text-sm text-slate-600 hover:text-white inline-flex items-center gap-1 mb-6">← Volver a subir</RouterLink>

      <div class="bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl p-6 sm:p-8 shadow-xl">
        <h1 class="text-xl font-semibold">Estado del procesamiento</h1>
        <p class="text-sm text-slate-600 mt-1 font-mono break-all">Job ID: {{ jobId }}</p>

        <div v-if="error" role="alert" class="mt-6 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3">
          <p class="text-sm text-red-300">{{ error }}</p>
        </div>

        <div v-if="!job && pollingStatus === 'polling' && !error" class="mt-8 flex flex-col items-center gap-3 py-8">
          <span class="h-8 w-8 animate-spin rounded-full border-2 border-brand-500/30 border-t-violet-500" />
          <p class="text-sm text-slate-600">Consultando estado...</p>
        </div>

        <div v-if="job" class="mt-6 space-y-6">
          <div class="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-slate-800/60 rounded-xl px-4 py-4 border border-slate-200/70 dark:border-slate-800 shadow-sm shadow-slate-100/80">
            <span class="text-sm text-slate-600">Estado</span>
            <span v-if="job.status === 'PENDING'" class="inline-flex items-center gap-2 rounded-full bg-amber-500/10 border border-amber-500/30 px-3 py-1 text-sm font-medium text-amber-300"><span class="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> En cola...</span>
            <span v-else-if="job.status === 'PROCESSING'" class="inline-flex items-center gap-2 rounded-full bg-sky-500/10 border border-sky-500/30 px-3 py-1 text-sm font-medium text-sky-300"><span class="h-4 w-4 animate-spin rounded-full border-2 border-sky-300/30 border-t-sky-300" /> Procesando video y generando clips...</span>
            <span v-else-if="job.status === 'COMPLETED'" class="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 text-sm font-medium text-emerald-300">✓ ¡Procesamiento Completado!</span>
            <span v-else-if="job.status === 'FAILED'" class="inline-flex items-center gap-2 rounded-full bg-red-500/10 border border-red-500/30 px-3 py-1 text-sm font-medium text-red-300">✕ Falló el procesamiento</span>
            <span v-else class="text-sm text-slate-600">{{ job.status }}</span>
          </div>

          <div v-if="job.status === 'PENDING'" class="rounded-xl bg-amber-500/5 border border-amber-500/20 p-4 flex gap-3">
            <span class="h-8 w-8 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-300 shrink-0">⏳</span>
            <div><p class="text-sm font-medium text-amber-200">En cola...</p><p class="text-sm text-slate-600 mt-1">Tu video está esperando a ser procesado. Esto se actualiza solo.</p></div>
          </div>

          <div v-if="job.status === 'PROCESSING'" class="rounded-xl bg-sky-500/5 border border-sky-500/20 p-4 flex gap-3">
            <span class="h-8 w-8 rounded-full bg-sky-500/20 flex items-center justify-center shrink-0"><span class="h-4 w-4 animate-spin rounded-full border-2 border-sky-300/30 border-t-sky-300" /></span>
            <div><p class="text-sm font-medium text-sky-200">Procesando video y generando clips...</p><p class="text-sm text-slate-600 mt-1">Puede tardar unos minutos. La página se actualiza automáticamente.</p></div>
          </div>

          <div v-if="job.status === 'COMPLETED'" class="space-y-4">
            <div class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-4 flex gap-3">
              <span class="h-8 w-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-300 shrink-0">✓</span>
              <div>
                <p class="text-sm font-medium text-emerald-200">¡Procesamiento Completado!</p>
                <p class="text-sm text-slate-600 mt-1">{{ clips.length > 0 ? `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}` : 'Tus clips ya están listos.' }}<span v-if="job.result_metadata?.engine" class="ml-2 text-xs text-slate-600">· motor: {{ job.result_metadata.engine }}</span></p>
              </div>
            </div>

            <div v-if="clips.length > 0" class="grid gap-3 sm:gap-4">
              <div v-for="(clip, idx) in clips" :key="`${clip.titulo}-${idx}`" class="rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200/70 dark:border-slate-800 shadow-sm shadow-slate-100/80 p-4 sm:p-5 flex flex-col gap-3">
                <div class="flex items-start justify-between gap-3">
                  <h3 class="text-sm sm:text-base font-semibold text-white leading-snug line-clamp-2">{{ clip.titulo }}</h3>
                  <span v-if="typeof clip.score === 'number'" class="shrink-0 inline-flex items-center rounded-full bg-gradient-to-r from-violet-600 to-indigo-600/15 border border-brand-500/30 px-2.5 py-1 text-xs font-semibold text-violet-300">Score {{ clip.score.toFixed(2) }}</span>
                </div>
                <p class="text-xs sm:text-sm font-mono text-slate-600 bg-white dark:bg-slate-900/70 rounded-lg px-3 py-2 border border-slate-200/70 dark:border-slate-800 shadow-sm shadow-slate-100/80">Inicio: {{ clip.inicio }} - Fin: {{ clip.fin }}</p>
                <p v-if="clip.transcript_preview" class="text-sm text-gray-300 leading-relaxed line-clamp-3 bg-white dark:bg-slate-900/40 rounded-lg px-3 py-2">{{ clip.transcript_preview }}</p>
                <p class="text-[11px] text-slate-600">Modo simulado — sin archivo recortado individual, timestamps informativos</p>
              </div>
            </div>

            <RouterLink v-if="clips.length === 0" :to="`/clips?job_id=${job.job_id ?? job.id}`" class="w-full inline-flex items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 px-4 transition">Ver clips generados →</RouterLink>
          </div>

          <div v-if="job.status === 'FAILED'" role="alert" class="rounded-xl bg-red-500/10 border border-red-500/30 p-4">
            <p class="text-sm font-medium text-red-300">Error en el procesamiento</p>
            <p class="text-sm text-red-300/80 mt-2 break-words">{{ job.error_message || 'El job falló sin mensaje detallado. Intenta subir el video nuevamente.' }}</p>
            <RouterLink to="/upload" class="mt-4 inline-flex rounded-xl bg-white dark:bg-slate-800 hover:bg-gray-700 border border-slate-200/70 dark:border-slate-800 shadow-sm shadow-slate-100/80 text-white text-sm font-medium py-2.5 px-4 transition">Intentar de nuevo</RouterLink>
          </div>

          <div class="pt-2 border-t border-slate-200 dark:border-slate-700 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-slate-600">
            <span>Creado: {{ new Date(job.created_at).toLocaleString() }}</span>
            <span>Actualizado: {{ new Date(job.updated_at).toLocaleString() }}</span>
          </div>
        </div>
      </div>

      <p class="text-center text-xs text-gray-600 mt-6">Se actualiza cada 2 segundos sin recargar la página</p>
    </div>
  </div>
</template>
