<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { metricsService, statsService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { MetricsResponse, StatsSummary } from '@/types/api'

const stats = ref<StatsSummary | null>(null)
const metrics = ref<MetricsResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

function formatHours(hours: number): string {
  if (hours === 0) return '0h'
  if (hours < 1) return `${Math.round(hours * 60)} min`
  if (hours % 1 === 0) return `${hours}h`
  return `${hours.toFixed(1)}h`
}

function scoreBadgeClass(score: number): string {
  if (score >= 71) return 'bg-[rgba(180,241,5,0.14)] text-[#B4F105] border-[rgba(180,241,5,0.3)] shadow-[0_0_12px_rgba(180,241,5,0.15)]'
  if (score >= 41) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  return 'bg-red-500/15 text-red-300 border-red-500/30'
}

function scoreLabel(score: number): string {
  if (score >= 71) return 'Alto'
  if (score >= 41) return 'Medio'
  return 'Bajo'
}

const maxCount = computed(() => {
  if (!stats.value) return 1
  return Math.max(1, ...stats.value.score_distribution.map((d) => d.count))
})

const barColors: Record<string, string> = {
  Bajo: '#ef4444',
  Medio: '#f59e0b',
  Alto: '#10b981',
}

const platformColors: Record<string, string> = {
  tiktok: '#EC4899',
  youtube: '#EF4444',
  instagram: '#8B5CF6',
}

const platformEntries = computed(() => {
  if (!metrics.value) return []
  return Object.entries(metrics.value.platform_distribution).map(([k, v]) => ({ platform: k, count: v }))
})

const hasPlatformData = computed(() => platformEntries.value.some((e) => e.count > 0))

const maxPlatform = computed(() => {
  if (platformEntries.value.length === 0) return 1
  return Math.max(1, ...platformEntries.value.map((e) => e.count))
})

const maxRecent = computed(() => {
  if (!metrics.value) return 1
  return Math.max(1, ...metrics.value.recent_activity.map((d) => Math.max(d.jobs, d.clips, d.minutes_processed)))
})

const isEmpty = computed(() => {
  if (!metrics.value) return false
  return metrics.value.total_jobs === 0 && metrics.value.total_clips === 0
})

async function fetchAll() {
  loading.value = true
  error.value = null
  try {
    const [s, m] = await Promise.all([statsService.getSummary(), metricsService.getMetrics()])
    stats.value = s
    metrics.value = m
  } catch (err: unknown) {
    if (err instanceof ApiError) error.value = err.detail
    else if (err instanceof Error) error.value = err.message
    else error.value = 'Error al cargar métricas'
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)
</script>

<template>
  <div class="min-h-screen bg-[#0B0F17] text-white">
    <div class="max-w-6xl mx-auto px-4 py-6 sm:py-8">
      <div class="mb-6 sm:mb-8">
        <div class="inline-flex items-center gap-2 mb-3 px-3 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.10)] text-[#B4F105] border border-[rgba(180,241,5,0.22)]">
          <span class="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.6)] animate-pulse" /> LIVE
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-[#F1F5F9]">Dashboard de Métricas</h1>
        <p class="text-sm text-[#94A3B8] mt-2">Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.</p>
      </div>

      <template v-if="loading">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div v-for="i in 4" :key="i" class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 animate-pulse">
            <div class="h-3 bg-[rgba(255,255,255,0.06)] rounded w-1/2 mb-4" />
            <div class="h-8 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-2" />
            <div class="h-3 bg-[rgba(255,255,255,0.04)] rounded w-2/3" />
          </div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
          <div class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-6 h-[320px] animate-pulse">
            <div class="h-4 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-6" />
            <div class="h-[240px] bg-[rgba(255,255,255,0.04)] rounded" />
          </div>
          <div class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-6 h-[320px] animate-pulse">
            <div class="h-4 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-6" />
            <div class="h-[240px] bg-[rgba(255,255,255,0.04)] rounded" />
          </div>
        </div>
      </template>

      <div v-else-if="error" role="alert" class="alert-custom alert-custom-danger">
        <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
        <div class="alert-custom-content">{{ error }}</div>
        <button class="btn-custom btn-custom-danger btn-custom-sm" @click="fetchAll">Reintentar</button>
      </div>

      <div v-else-if="metrics && isEmpty" class="rounded-2xl bg-[#121824] border border-dashed border-[rgba(180,241,5,0.18)] p-10 text-center shadow-xl">
        <div class="h-12 w-12 rounded-full bg-[rgba(180,241,5,0.10)] border border-[rgba(180,241,5,0.22)] flex items-center justify-center text-xl mx-auto text-[#B4F105]">📊</div>
        <p class="text-sm font-bold text-[#F1F5F9] mt-4">Aún no tienes métricas</p>
        <p class="text-xs text-[#94A3B8] mt-1 max-w-[300px] mx-auto">Cuando proceses tu primer video verás aquí clips generados, horas ahorradas y actividad de los últimos 7 días.</p>
        <RouterLink to="/upload" class="btn-custom btn-custom-primary mt-5 shadow-[0_0_20px_rgba(180,241,5,0.3)]"><i class="bi bi-lightning-charge-fill" /> Subir primer video</RouterLink>
      </div>

      <template v-else-if="metrics && !isEmpty">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="kpi-card">
            <div class="flex items-center justify-between"><p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Total Videos / Jobs</p><span class="kpi-accent"><i class="bi bi-film" /></span></div>
            <p class="text-3xl font-extrabold mt-3 text-white tracking-tight">{{ metrics.total_jobs }}</p>
            <p class="text-xs text-[#94A3B8] mt-1">{{ stats ? `${stats.total_videos} videos subidos` : 'Jobs procesados' }}</p>
          </div>
          <div class="kpi-card">
            <div class="flex items-center justify-between"><p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Total Clips</p><span class="kpi-accent"><i class="bi bi-collection-play" /></span></div>
            <p class="text-3xl font-extrabold mt-3 text-white tracking-tight">{{ metrics.total_clips }}</p>
            <p class="text-xs text-[#94A3B8] mt-1">Clips virales extraídos</p>
          </div>
          <div class="kpi-card">
            <div class="flex items-center justify-between"><p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Tiempo Ahorrado</p><span class="kpi-accent !bg-[rgba(180,241,5,0.14)] !border-[rgba(180,241,5,0.25)] !text-[#B4F105]"><i class="bi bi-lightning-charge" /></span></div>
            <p class="text-3xl font-extrabold mt-3 text-[#B4F105] tracking-tight" style="text-shadow: 0 0 16px rgba(180,241,5,0.35)">{{ formatHours(metrics.time_saved_hours) }}</p>
            <p class="text-xs text-[#94A3B8] mt-1">Estimado · {{ metrics.total_minutes_processed }} min procesados</p>
          </div>
          <div class="kpi-card">
            <template v-if="stats">
              <p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Promedio Viralidad</p>
              <div class="flex items-center gap-3 mt-3">
                <p class="text-3xl font-extrabold text-white tracking-tight">{{ stats.avg_score.toFixed(1) }}</p>
                <span class="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold" :class="scoreBadgeClass(stats.avg_score)">{{ scoreLabel(stats.avg_score) }}</span>
              </div>
              <p class="text-xs text-[#94A3B8] mt-1">Score promedio de tus clips</p>
            </template>
            <template v-else>
              <p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Minutos Procesados</p>
              <p class="text-3xl font-extrabold mt-3 text-white">{{ metrics.total_minutes_processed }}</p>
              <p class="text-xs text-[#94A3B8] mt-1">Acumulado total</p>
            </template>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
          <div class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 sm:p-6 shadow-xl">
            <h2 class="text-sm font-semibold text-[#F1F5F9]">{{ hasPlatformData ? 'Distribución por Plataforma' : 'Distribución por Score' }}</h2>
            <p class="text-xs text-[#94A3B8] mt-1">{{ hasPlatformData ? 'Clips agrupados por red social objetivo' : 'Conteo de clips agrupados por rango de viralidad' }}</p>
            <div v-if="hasPlatformData" class="mt-6 space-y-4">
              <div v-for="entry in platformEntries" :key="entry.platform" class="space-y-1.5">
                <div class="flex items-center justify-between text-xs">
                  <span class="font-medium capitalize" :style="{ color: platformColors[entry.platform] ?? '#9ca3af' }">{{ entry.platform }}</span>
                  <span class="text-gray-400 font-mono">{{ entry.count }} clips</span>
                </div>
                <div class="h-8 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden p-1 border border-[rgba(255,255,255,0.04)]">
                  <div
                    class="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2"
                    :style="{ width: `${(entry.count / maxPlatform) * 100}%`, backgroundColor: platformColors[entry.platform] ?? '#6366f1', minWidth: entry.count > 0 ? '32px' : '0' }"
                  >
                    <span v-if="entry.count > 0" class="text-[11px] font-bold text-white">{{ entry.count }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="mt-6 space-y-4">
              <div v-for="item in stats?.score_distribution ?? []" :key="item.range" class="space-y-1.5">
                <div class="flex items-center justify-between text-xs">
                  <span class="font-medium" :style="{ color: barColors[item.label] ?? '#9ca3af' }">{{ item.label }} ({{ item.range }})</span>
                  <span class="text-[#94A3B8] font-mono">{{ item.count }} clips</span>
                </div>
                <div class="h-8 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden p-1 border border-[rgba(255,255,255,0.04)]">
                  <div
                    class="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2"
                    :style="{ width: `${(item.count / maxCount) * 100}%`, backgroundColor: barColors[item.label] ?? '#6366f1', minWidth: item.count > 0 ? '32px' : '0' }"
                  >
                    <span v-if="item.count > 0" class="text-[11px] font-bold text-white">{{ item.count }}</span>
                  </div>
                </div>
              </div>
              <div class="flex items-center justify-center gap-4 mt-6">
                <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full" style="background:#ef4444" /> 0-40 Bajo</span>
                <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full" style="background:#f59e0b" /> 41-70 Medio</span>
                <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full" style="background:#10b981" /> 71-100 Alto</span>
              </div>
            </div>
          </div>

          <div class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 sm:p-6 shadow-xl">
            <h2 class="text-sm font-semibold text-[#F1F5F9]">Actividad Reciente</h2>
            <p class="text-xs text-[#94A3B8] mt-1">Últimos 7 días · jobs, clips y minutos procesados</p>
            <div class="mt-6 space-y-3">
              <div v-for="day in metrics.recent_activity" :key="day.date" class="space-y-1.5">
                <div class="flex items-center justify-between text-xs">
                  <span class="font-mono text-gray-400">{{ day.date.slice(5) }}</span>
                  <span class="text-gray-500">{{ day.jobs }} jobs · {{ day.clips }} clips · {{ day.minutes_processed }} min</span>
                </div>
                <div class="h-8 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden p-1 flex gap-1 border border-[rgba(255,255,255,0.04)]">
                  <div
                    class="h-full rounded-full bg-violet-500 transition-all flex items-center justify-center"
                    :style="{ width: `${(day.jobs / maxRecent) * 40}%`, minWidth: day.jobs > 0 ? '24px' : '0' }"
                    :title="`${day.jobs} jobs`"
                  >
                    <span v-if="day.jobs > 0" class="text-[10px] font-bold text-white">{{ day.jobs }}</span>
                  </div>
                  <div
                    class="h-full rounded-full bg-emerald-500 transition-all flex items-center justify-center"
                    :style="{ width: `${(day.clips / maxRecent) * 40}%`, minWidth: day.clips > 0 ? '24px' : '0' }"
                    :title="`${day.clips} clips`"
                  >
                    <span v-if="day.clips > 0" class="text-[10px] font-bold text-white">{{ day.clips }}</span>
                  </div>
                  <div
                    class="h-full rounded-full bg-amber-500 transition-all flex items-center justify-center"
                    :style="{ width: `${(day.minutes_processed / maxRecent) * 20}%`, minWidth: day.minutes_processed > 0 ? '24px' : '0' }"
                    :title="`${day.minutes_processed} min`"
                  >
                    <span v-if="day.minutes_processed > 0" class="text-[10px] font-bold text-white">{{ day.minutes_processed }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="flex items-center justify-center gap-4 mt-6">
              <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full bg-violet-500" /> Jobs</span>
              <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Clips</span>
              <span class="inline-flex items-center gap-1.5 text-xs text-gray-400"><span class="h-2.5 w-2.5 rounded-full bg-amber-500" /> Min</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
