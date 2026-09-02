<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { statsService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { StatsSummary } from '@/types/api'

const data = ref<StatsSummary | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

function formatTime(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

function scoreBadgeClass(score: number): string {
  if (score >= 71) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (score >= 41) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  return 'bg-red-500/15 text-red-300 border-red-500/30'
}

function scoreLabel(score: number): string {
  if (score >= 71) return 'Alto'
  if (score >= 41) return 'Medio'
  return 'Bajo'
}

function statusBadgeClass(status: string): string {
  const s = status.toUpperCase()
  if (s === 'COMPLETED') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (s === 'PROCESSING') return 'bg-sky-500/15 text-sky-300 border-sky-500/30'
  if (s === 'PENDING') return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  if (s === 'FAILED') return 'bg-red-500/15 text-red-300 border-red-500/30'
  return 'bg-gray-700 text-gray-300 border-gray-600'
}

const maxCount = computed(() => {
  if (!data.value) return 1
  return Math.max(1, ...data.value.score_distribution.map((d) => d.count))
})

const barColors: Record<string, string> = {
  Bajo: '#ef4444',
  Medio: '#f59e0b',
  Alto: '#10b981',
}

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await statsService.getSummary()
  } catch (err: unknown) {
    if (err instanceof ApiError) error.value = err.detail
    else if (err instanceof Error) error.value = err.message
    else error.value = 'Error al cargar estadísticas'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-white">
    <div class="max-w-6xl mx-auto px-4 py-6 sm:py-8">
      <div class="mb-6 sm:mb-8">
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">Dashboard de Métricas</h1>
        <p class="text-sm text-gray-400 mt-2">Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.</p>
      </div>

      <!-- Skeletons -->
      <template v-if="loading">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div v-for="i in 4" :key="i" class="rounded-2xl bg-gray-900 border border-gray-800 p-5 animate-pulse">
            <div class="h-3 bg-gray-800 rounded w-1/2 mb-4" />
            <div class="h-8 bg-gray-800 rounded w-1/3 mb-2" />
            <div class="h-3 bg-gray-800 rounded w-2/3" />
          </div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-6 h-[320px] animate-pulse">
            <div class="h-4 bg-gray-800 rounded w-1/3 mb-6" />
            <div class="h-[240px] bg-gray-800 rounded" />
          </div>
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-6 h-[320px] animate-pulse">
            <div class="h-4 bg-gray-800 rounded w-1/3 mb-6" />
            <div class="h-20 bg-gray-800 rounded" />
          </div>
        </div>
      </template>

      <!-- Error -->
      <div v-else-if="error" role="alert" class="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-center">
        <p class="text-sm text-red-300">{{ error }}</p>
        <button class="mt-4 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-xl px-4 py-2 transition" @click="load">Reintentar</button>
      </div>

      <!-- Data -->
      <template v-else-if="data">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
            <p class="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Videos Subidos</p>
            <p class="text-3xl font-bold mt-2">{{ data.total_videos }}</p>
            <p class="text-xs text-gray-500 mt-1">Videos procesados en tu cuenta</p>
          </div>
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
            <p class="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Clips Generados</p>
            <p class="text-3xl font-bold mt-2">{{ data.total_clips }}</p>
            <p class="text-xs text-gray-500 mt-1">Clips virales extraídos</p>
          </div>
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
            <p class="text-xs font-medium text-gray-400 uppercase tracking-wide">Promedio de Viralidad</p>
            <div class="flex items-center gap-3 mt-2">
              <p class="text-3xl font-bold">{{ data.avg_score.toFixed(1) }}</p>
              <span class="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold" :class="scoreBadgeClass(data.avg_score)">{{ scoreLabel(data.avg_score) }}</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">Score promedio de todos tus clips</p>
          </div>
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
            <p class="text-xs font-medium text-gray-400 uppercase tracking-wide">Tiempo Ahorrado</p>
            <p class="text-3xl font-bold mt-2">{{ formatTime(data.estimated_time_saved_minutes) }}</p>
            <p class="text-xs text-gray-500 mt-1">Estimado · {{ data.total_clips }} × 15 min</p>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
          <!-- Chart - Tailwind bars -->
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5 sm:p-6">
            <h2 class="text-sm font-semibold text-white">Distribución por Score</h2>
            <p class="text-xs text-gray-500 mt-1">Conteo de clips agrupados por rango de viralidad</p>
            <div class="mt-6 space-y-4">
              <div v-for="item in data.score_distribution" :key="item.range" class="space-y-1.5">
                <div class="flex items-center justify-between text-xs">
                  <span class="font-medium" :style="{ color: barColors[item.label] ?? '#9ca3af' }">{{ item.label }} ({{ item.range }})</span>
                  <span class="text-gray-400 font-mono">{{ item.count }} clips</span>
                </div>
                <div class="h-8 bg-gray-800 rounded-full overflow-hidden p-1">
                  <div
                    class="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2"
                    :style="{ width: `${(item.count / maxCount) * 100}%`, backgroundColor: barColors[item.label] ?? '#6366f1', minWidth: item.count > 0 ? '32px' : '0' }"
                  >
                    <span v-if="item.count > 0" class="text-[11px] font-bold text-white">{{ item.count }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="flex items-center justify-center gap-4 mt-6">
              <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full" style="background:#ef4444" /> 0-40 Bajo</span>
              <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full" style="background:#f59e0b" /> 41-70 Medio</span>
              <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full" style="background:#10b981" /> 71-100 Alto</span>
            </div>
          </div>

          <!-- Recent job -->
          <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5 sm:p-6 flex flex-col">
            <h2 class="text-sm font-semibold text-white">Actividad Reciente</h2>
            <p class="text-xs text-gray-500 mt-1">Último job de procesamiento</p>

            <div v-if="data.recent_job" class="mt-6 rounded-xl bg-gray-800/60 border border-gray-800 p-4 sm:p-5 flex flex-col gap-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-xs text-gray-400">Job ID</p>
                  <p class="text-sm font-mono text-white truncate">{{ data.recent_job.id }}</p>
                  <p class="text-xs text-gray-500 mt-1">Creado: {{ new Date(data.recent_job.created_at).toLocaleString() }}</p>
                </div>
                <span class="shrink-0 inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold" :class="statusBadgeClass(data.recent_job.status)">{{ data.recent_job.status }}</span>
              </div>
              <RouterLink :to="`/jobs/${data.recent_job.id}`" class="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium py-2.5 px-4 transition">Ver Job →</RouterLink>
            </div>

            <div v-else class="mt-6 flex flex-1 flex-col items-center justify-center rounded-xl bg-gray-800/40 border border-dashed border-gray-700 p-8 text-center">
              <div class="h-12 w-12 rounded-full bg-gray-800 flex items-center justify-center text-xl">🎬</div>
              <p class="text-sm font-medium text-gray-200 mt-4">Aún no hay actividad</p>
              <p class="text-xs text-gray-500 mt-1 max-w-[260px]">Sube tu primer video para generar clips y ver métricas aquí.</p>
              <RouterLink to="/upload" class="mt-5 inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium py-2.5 px-5 transition">Subir primer video</RouterLink>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
