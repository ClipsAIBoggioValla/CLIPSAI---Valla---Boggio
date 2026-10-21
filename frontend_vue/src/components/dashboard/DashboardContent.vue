<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="kpi-card">
      <div class="flex items-center justify-between">
        <p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Total Videos / Jobs</p>
        <span class="kpi-accent"><i class="bi bi-film" /></span>
      </div>
      <p class="text-3xl font-extrabold mt-3 text-white tracking-tight">{{ metrics.total_jobs }}</p>
      <p class="text-xs text-[#94A3B8] mt-1">{{ stats ? `${stats.total_videos} videos subidos` : 'Jobs procesados' }}</p>
    </div>
    <div class="kpi-card">
      <div class="flex items-center justify-between">
        <p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Total Clips</p>
        <span class="kpi-accent"><i class="bi bi-collection-play" /></span>
      </div>
      <p class="text-3xl font-extrabold mt-3 text-white tracking-tight">{{ metrics.total_clips }}</p>
      <p class="text-xs text-[#94A3B8] mt-1">Clips virales extraídos</p>
    </div>
    <div class="kpi-card">
      <div class="flex items-center justify-between">
        <p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Tiempo Ahorrado</p>
        <span class="kpi-accent !bg-[rgba(180,241,5,0.14)] !border-[rgba(180,241,5,0.25)] !text-[#B4F105]"><i class="bi bi-lightning-charge" /></span>
      </div>
      <p class="text-3xl font-extrabold mt-3 text-[#B4F105] tracking-tight" style="text-shadow: 0 0 16px rgba(180,241,5,0.35)">{{ formatHours(metrics.time_saved_hours) }}</p>
      <p class="text-xs text-[#94A3B8] mt-1">Estimado · {{ metrics.total_minutes_processed }} min procesados</p>
    </div>
    <div class="kpi-card">
      <p class="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Promedio Viralidad</p>
      <div class="flex items-center gap-3 mt-3">
        <p class="text-3xl font-extrabold text-white tracking-tight">{{ stats?.avg_score.toFixed(1) ?? 0 }}</p>
        <span class="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold" :class="scoreBadgeClass(stats?.avg_score ?? 0)">{{ scoreLabel(stats?.avg_score ?? 0) }}</span>
      </div>
      <p class="text-xs text-[#94A3B8] mt-1">Score promedio de tus clips</p>
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
            <div class="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2" :style="{ width: `${(entry.count / maxPlatform) * 100}%`, backgroundColor: platformColors[entry.platform] ?? '#6366f1', minWidth: entry.count > 0 ? '32px' : '0' }">
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
            <div class="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2" :style="{ width: `${(item.count / maxCount) * 100}%`, backgroundColor: barColors[item.label] ?? '#6366f1', minWidth: item.count > 0 ? '32px' : '0' }">
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
            <div class="h-full rounded-full bg-violet-500 transition-all flex items-center justify-center" :style="{ width: `${(day.jobs / maxRecent) * 40}%`, minWidth: day.jobs > 0 ? '24px' : '0' }" :title="`${day.jobs} jobs`">
              <span v-if="day.jobs > 0" class="text-[10px] font-bold text-white">{{ day.jobs }}</span>
            </div>
            <div class="h-full rounded-full bg-emerald-500 transition-all flex items-center justify-center" :style="{ width: `${(day.clips / maxRecent) * 40}%`, minWidth: day.clips > 0 ? '24px' : '0' }" :title="`${day.clips} clips`">
              <span v-if="day.clips > 0" class="text-[10px] font-bold text-white">{{ day.clips }}</span>
            </div>
            <div class="h-full rounded-full bg-amber-500 transition-all flex items-center justify-center" :style="{ width: `${(day.minutes_processed / maxRecent) * 20}%`, minWidth: day.minutes_processed > 0 ? '24px' : '0' }" :title="`${day.minutes_processed} min`">
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

<script setup lang="ts">
import { computed } from 'vue'
import type { MetricsResponse, StatsSummary } from '@/types/api'

const props = defineProps<{
  stats: StatsSummary | null
  metrics: MetricsResponse
}>()

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
const barColors: Record<string, string> = { Bajo: '#ef4444', Medio: '#f59e0b', Alto: '#10b981' }
const platformColors: Record<string, string> = { tiktok: '#EC4899', youtube: '#EF4444', instagram: '#8B5CF6' }
const platformEntries = computed(() => Object.entries(props.metrics.platform_distribution).map(([k, v]) => ({ platform: k, count: v })))
const hasPlatformData = computed(() => platformEntries.value.some((e) => e.count > 0))
const maxPlatform = computed(() => (platformEntries.value.length ? Math.max(1, ...platformEntries.value.map((e) => e.count)) : 1))
const maxCount = computed(() => (props.stats ? Math.max(1, ...props.stats.score_distribution.map((d) => d.count)) : 1))
const maxRecent = computed(() => (props.metrics ? Math.max(1, ...props.metrics.recent_activity.map((d) => Math.max(d.jobs, d.clips, d.minutes_processed))) : 1))
</script>
EOF
echo "DashboardContent.vue written ($(wc -l < frontend_vue/src/components/dashboard/DashboardContent.vue) lines)"