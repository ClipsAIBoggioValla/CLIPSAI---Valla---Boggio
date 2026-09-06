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
  <div class="max-w-2xl mx-auto">
    <RouterLink to="/upload" class="btn-custom btn-custom-light mb-6"><i class="bi bi-arrow-left" /> Volver a subir</RouterLink>

    <div class="card-spark">
      <h1 class="card-title">Estado del procesamiento</h1>
      <p class="text-sm font-mono break-all" style="color: var(--text-muted-green)">Job ID: {{ jobId }}</p>

      <div v-if="error" role="alert" class="alert-custom alert-custom-danger mt-6">
        <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
        <div class="alert-custom-content">{{ error }}</div>
      </div>

      <div v-if="!job && pollingStatus === 'polling' && !error" class="mt-8 flex flex-col items-center gap-3 py-8">
        <span class="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
        <p class="text-sm" style="color: var(--text-muted-green)">Consultando estado...</p>
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
            <div class="alert-custom-content"><strong>¡Procesamiento Completado!</strong> {{ clips.length > 0 ? `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}` : 'Tus clips ya están listos.' }}<span v-if="job.result_metadata?.engine" class="ml-2 text-xs" style="color: var(--text-muted-green)">· motor: {{ job.result_metadata.engine }}</span></div>
          </div>

          <div v-if="clips.length > 0" class="grid gap-3 sm:gap-4">
            <div v-for="(clip, idx) in clips" :key="`${clip.titulo}-${idx}`" class="card-spark flex flex-col gap-3" style="padding: 1.25rem">
              <div class="flex items-start justify-between gap-3">
                <h3 class="text-sm font-bold leading-snug line-clamp-2" style="color: var(--text-main)">{{ clip.titulo }}</h3>
                <span v-if="typeof clip.score === 'number'" class="badge-table success">Score {{ clip.score.toFixed(2) }}</span>
              </div>
              <p class="text-xs font-mono rounded-lg px-3 py-2 border" style="color: var(--text-muted-green); background-color: var(--bs-body-bg); border-color: var(--border-light)">Inicio: {{ clip.inicio }} - Fin: {{ clip.fin }}</p>
              <p v-if="clip.transcript_preview" class="text-sm leading-relaxed line-clamp-3 rounded-lg px-3 py-2" style="color: var(--text-main); background-color: var(--bs-body-bg)">{{ clip.transcript_preview }}</p>
              <p class="text-xs" style="color: var(--text-muted-green)">Modo simulado — sin archivo recortado individual, timestamps informativos</p>
            </div>
          </div>

          <RouterLink v-if="clips.length === 0" :to="`/clips?job_id=${job.job_id ?? job.id}`" class="btn-custom btn-custom-primary w-full justify-center">Ver clips generados <i class="bi bi-arrow-right" /></RouterLink>
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
