<template>
  <div class="min-h-screen bg-[#0B0F17] text-white">
    <div class="max-w-6xl mx-auto px-4 py-6 sm:py-8">
      <div v-if="activeJobId" class="rounded-xl border border-[rgba(180,241,5,0.22)] bg-[rgba(180,241,5,0.08)] px-4 py-3 flex items-center justify-between gap-3 mb-6">
        <div class="flex items-center gap-2 text-sm font-bold text-[#B4F105]">
          <span class="h-2 w-2 rounded-full bg-[#B4F105] animate-pulse" /> Procesamiento activo
        </div>
        <RouterLink :to="`/jobs/${activeJobId}`" class="btn-custom btn-custom-primary btn-custom-sm">Ver progreso → <i class="bi bi-arrow-right" /></RouterLink>
      </div>
      <div class="mb-6 sm:mb-8">
        <div class="inline-flex items-center gap-2 mb-3 px-3 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.10)] text-[#B4F105] border border-[rgba(180,241,5,0.22)]">
          <span class="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.6)] animate-pulse" /> LIVE
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight" style="color: #F1F5F9">Dashboard de Métricas</h1>
        <p class="text-sm mt-2" style="color: #94A3B8">Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.</p>
      </div>

      <div class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-4 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <span class="h-9 w-9 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000]"><i class="bi bi-youtube" /></span>
          <div>
            <p class="text-sm font-bold text-white">YouTube — OAuth 2.0 (Issue #24)</p>
            <p class="text-xs text-[#94A3B8]">Prueba el conector: GET /auth/social/youtube/connect</p>
          </div>
        </div>
        <RouterLink to="/dashboard/integrations" class="btn-custom btn-custom-primary flex items-center gap-2 whitespace-nowrap" data-testid="go-integrations"><i class="bi bi-box-arrow-up-right" /> Conectar YouTube</RouterLink>
      </div>

      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 animate-pulse">
          <div class="h-3 bg-[rgba(255,255,255,0.06)] rounded w-1/2 mb-4" />
          <div class="h-8 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-2" />
          <div class="h-3 bg-[rgba(255,255,255,0.04)] rounded w-2/3" />
        </div>
      </div>

      <div v-if="error && !loading" role="alert" class="alert-custom alert-custom-danger">
        <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
        <div class="alert-custom-content">{{ error }}</div>
        <button class="btn-custom btn-custom-danger btn-custom-sm" @click="fetchAll">Reintentar</button>
      </div>

      <div v-if="!loading && !error && isEmpty" class="rounded-2xl bg-[#121824] border border-dashed border-[rgba(180,241,5,0.18)] p-10 text-center shadow-xl">
        <div class="h-12 w-12 rounded-full bg-[rgba(180,241,5,0.10)] border border-[rgba(180,241,5,0.22)] flex items-center justify-center text-xl mx-auto text-[#B4F105]">📊</div>
        <p class="text-sm font-bold text-[#F1F5F9] mt-4">Aún no tienes métricas</p>
        <p class="text-xs text-[#94A3B8] mt-1 max-w-[300px] mx-auto">Cuando proceses tu primer video verás aquí clips generados, horas ahorradas y actividad de los últimos 7 días.</p>
        <RouterLink to="/upload" class="btn-custom btn-custom-primary mt-5 shadow-[0_0_20px_rgba(180,241,5,0.3)]"><i class="bi bi-lightning-charge-fill" /> Subir primer video</RouterLink>
      </div>

      <DashboardContent v-if="!loading && !error && metrics && !isEmpty" :stats="stats" :metrics="metrics" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { metricsService, statsService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { MetricsResponse, StatsSummary } from '@/types/api'
import DashboardContent from '@/components/dashboard/DashboardContent.vue'

const stats = ref<StatsSummary | null>(null)
const metrics = ref<MetricsResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const activeJobId = ref<string | null>(null)

onMounted(() => {
  try {
    const id = localStorage.getItem('clipsai_active_job_id')
    if (id) activeJobId.value = id
  } catch {}
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

onMounted(() => { fetchAll() })

const isEmpty = computed(() => !!metrics.value && metrics.value.total_jobs === 0 && metrics.value.total_clips === 0)
</script>
EOF
echo "written ($(wc -l < frontend_vue/src/views/DashboardView.vue) lines)"