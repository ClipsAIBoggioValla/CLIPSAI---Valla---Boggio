<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clipService } from '@/api/services'
import type { ClipListResponse, ClipSortBy } from '@/types/api'
import { ApiError } from '@/types/api'

type ViewMode = 'grid' | 'list'

const route = useRoute()
const router = useRouter()
const routeQ = computed(() => (route.query.q as string) ?? '')
const q = ref(routeQ.value)
const debouncedQ = ref(routeQ.value)
const minScore = ref('')
const sortBy = ref<ClipSortBy>('created_at_desc')
const page = ref(1)
const limit = 10
const viewMode = ref<ViewMode>('grid')

const data = ref<ClipListResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

watch(routeQ, (v) => {
  if (v !== q.value) {
    q.value = v
    debouncedQ.value = v
  }
})

watch(debouncedQ, (v) => {
  const current = (route.query.q as string) ?? ''
  if (v !== current) {
    const query: Record<string, string> = { ...(route.query as Record<string, string>) }
    if (v) query.q = v
    else delete query.q
    router.replace({ path: route.path, query })
  }
})

let debounceTimer: number | undefined
watch(q, (v) => {
  window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => { debouncedQ.value = v }, 350)
})

watch([debouncedQ, minScore, sortBy], () => {
  page.value = 1
})

function scoreBadge(score: number | null) {
  if (score === null || score === undefined) return 'score-badge-neon low'
  if (score >= 70) return 'score-badge-neon high'
  if (score >= 40) return 'score-badge-neon mid'
  return 'score-badge-neon low'
}

function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—'
  return score.toFixed(1)
}

function formatRange(start: number, end: number): string {
  return `${start.toFixed(1)}s — ${end.toFixed(1)}s`
}

async function fetchClips() {
  loading.value = true
  error.value = null
  try {
    data.value = await clipService.getClips({
      q: debouncedQ.value || undefined,
      min_score: minScore.value ? Number(minScore.value) : undefined,
      sort_by: sortBy.value,
      page: page.value,
      limit,
    })
  } catch (err: unknown) {
    if (err instanceof ApiError) error.value = err.detail
    else if (err instanceof Error) error.value = err.message
    else error.value = 'Error al cargar clips'
  } finally {
    loading.value = false
  }
}

watch([debouncedQ, minScore, sortBy, page], fetchClips)
onMounted(fetchClips)

const hasFilters = () => debouncedQ.value !== '' || minScore.value !== '' || sortBy.value !== 'created_at_desc'

function resetFilters() {
  q.value = ''
  debouncedQ.value = ''
  minScore.value = ''
  sortBy.value = 'created_at_desc'
  page.value = 1
  const query: Record<string, string> = { ...(route.query as Record<string, string>) }
  delete query.q
  router.replace({ path: route.path, query })
}
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <div class="page-header" style="margin-bottom: 2rem">
      <div>
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]"><i class="bi bi-collection-play" style="font-size: 1.15rem" /></span>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]"><i class="bi bi-stars" /> Biblioteca</span>
          <span v-if="data" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border bg-[rgba(180,241,5,0.10)] text-[#B4F105] border-[rgba(180,241,5,0.22)]">{{ data.total }} clips</span>
        </div>
        <h1 class="page-title" style="margin-bottom: 0; font-size: 2.25rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; color: #F1F5F9">Biblioteca de Clips</h1>
        <p class="page-subtitle" style="margin-bottom: 0; margin-top: 0.7rem; font-size: 0.92rem; font-weight: 500; color: #94A3B8; line-height: 1.6; max-width: 640px">Explora, busca y gestiona todos tus clips generados con filtros inteligentes y paginación fluida.</p>
      </div>
    </div>

    <div class="flex flex-col md:flex-row items-center justify-between gap-4 p-3 bg-[#121824] rounded-xl border border-white/10" style="margin-bottom: 1rem; min-height: 56px">
      <div class="relative flex-1 max-w-md w-full">
        <i class="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" style="font-size: 0.9rem" />
        <input v-model="q" type="text" placeholder="Buscar por título o transcripción..." class="w-full pl-9 pr-4 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:border-[#B4F105] transition-colors" />
      </div>
      <div class="flex items-center gap-3 w-full md:w-auto justify-end">
        <select v-model="minScore" class="bg-[#0B0F17] text-xs text-white border border-white/10 rounded-lg px-3 py-2 cursor-pointer focus:outline-none hover:border-white/20 transition-colors">
          <option value="">Todos los scores</option>
          <option value="70">+70 Alto</option>
          <option value="40">+40 Medio</option>
        </select>
        <select v-model="sortBy" class="bg-[#0B0F17] text-xs text-white border border-white/10 rounded-lg px-3 py-2 cursor-pointer focus:outline-none hover:border-white/20 transition-colors">
          <option value="created_at_desc">Más recientes</option>
          <option value="created_at_asc">Más antiguos</option>
          <option value="score_desc">Mayor score</option>
          <option value="score_asc">Menor score</option>
        </select>
        <div class="py-1 px-1 bg-[#0B0F17] border border-white/10 rounded-lg flex items-center gap-1">
          <button type="button" class="px-3 py-1.5 rounded-md text-xs font-bold transition" :class="viewMode === 'grid' ? 'bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'text-[#94A3B8] hover:text-white'" @click="viewMode = 'grid'">⊞ Grid</button>
          <button type="button" class="px-3 py-1.5 rounded-md text-xs font-bold transition" :class="viewMode === 'list' ? 'bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'text-[#94A3B8] hover:text-white'" @click="viewMode = 'list'">☰ Lista</button>
        </div>
      </div>
    </div>
    <div v-if="hasFilters()" class="flex items-center gap-2 mb-3">
      <span class="text-xs font-bold text-[#94A3B8]">Filtros activos</span>
      <button class="btn-custom btn-custom-light btn-custom-sm !py-1 !text-xs" @click="resetFilters">Resetear filtros</button>
    </div>

    <div v-if="loading" :class="viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'">
      <div v-for="i in 6" :key="i" class="card-spark animate-pulse">
        <div class="h-4 rounded w-3/4 mb-3 bg-[rgba(255,255,255,0.06)]" />
        <div class="h-3 rounded w-1/2 mb-4 bg-[rgba(255,255,255,0.04)]" />
        <div class="h-10 rounded mb-3 bg-[rgba(255,255,255,0.04)]" />
        <div class="h-3 rounded w-1/3 bg-[rgba(255,255,255,0.04)]" />
      </div>
    </div>

    <div v-else-if="error" role="alert" class="alert-custom alert-custom-danger">
      <i class="bi bi-exclamation-circle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
      <button class="btn-custom btn-custom-danger btn-custom-sm" @click="fetchClips">Reintentar</button>
    </div>

    <div v-else-if="data && data.items.length === 0" class="card-spark text-center" style="border-style: dashed; padding: 2.5rem; border-color: rgba(180,241,5,0.18)">
      <div class="h-12 w-12 rounded-full flex items-center justify-center text-xl mx-auto bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.06)]">🎬</div>
      <p class="text-sm font-bold mt-4" style="color: #F1F5F9">No hay clips que coincidan</p>
      <p class="text-xs mt-1" style="color: #94A3B8">Prueba ajustando la búsqueda, el filtro de score o el ordenamiento.</p>
      <button v-if="hasFilters()" class="btn-custom btn-custom-primary mt-5" @click="resetFilters">Limpiar filtros</button>
    </div>

    <template v-else-if="data && data.items.length > 0">
      <div v-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="clip in data.items" :key="clip.id" class="clip-card" style="margin-bottom: 0">
          <div class="flex items-start justify-between gap-2">
            <h3 class="text-sm font-bold line-clamp-2 flex-1" style="color: #F1F5F9">{{ clip.title || 'Clip sin título' }}</h3>
            <span :class="scoreBadge(clip.score)">{{ formatScore(clip.score) }}</span>
          </div>
          <p class="text-xs font-mono px-2.5 py-1.5 rounded-full border inline-flex items-center gap-1.5" style="color: #94A3B8; background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.08)"><i class="bi bi-clock" style="font-size: 0.7rem" /> {{ formatRange(clip.start_time, clip.end_time) }} · {{ new Date(clip.created_at).toLocaleDateString() }}</p>
          <p v-if="clip.transcript" class="text-sm line-clamp-3 leading-relaxed rounded-xl px-3 py-2.5 border" style="color: #CBD5E1; background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.06)">{{ clip.transcript }}</p>
          <p v-else class="text-xs italic" style="color: #64748B">Sin transcripción disponible</p>
          <div class="flex items-center gap-1.5 pt-1"><span class="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.5)]" /><span class="text-[11px] font-semibold tracking-wide uppercase" style="color: #94A3B8">Listo para publicar</span></div>
        </div>
      </div>

      <div v-else class="table-card-custom">
        <div class="table-responsive" style="overflow-x: auto">
          <table class="table-custom">
            <thead>
              <tr>
                <th>Título</th>
                <th>Score</th>
                <th>Inicio - Fin</th>
                <th>Fecha</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="clip in data.items" :key="clip.id">
                <td>
                  <p class="font-bold line-clamp-1" style="color: var(--text-main)">{{ clip.title || 'Sin título' }}</p>
                  <p v-if="clip.transcript" class="text-xs line-clamp-1 mt-1" style="color: var(--text-muted-green)">{{ clip.transcript }}</p>
                </td>
                <td><span :class="scoreBadge(clip.score)">{{ formatScore(clip.score) }}</span></td>
                <td class="font-mono text-xs" style="color: var(--text-muted-green)">{{ formatRange(clip.start_time, clip.end_time) }}</td>
                <td class="text-xs" style="color: var(--text-muted-green)">{{ new Date(clip.created_at).toLocaleDateString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="table-footer-control" style="border-radius: var(--radius-xl); margin-top: 1rem">
        <span class="table-pagination-info">Mostrando <strong style="color: var(--text-main)">{{ data.items.length }}</strong> de <strong style="color: var(--text-main)">{{ data.total }}</strong> clips · Página {{ data.page }} de {{ data.total_pages || 1 }}</span>
        <div class="flex items-center gap-2">
          <button :disabled="page <= 1" class="btn-custom btn-custom-light btn-custom-sm" @click="page = Math.max(1, page - 1)">Anterior</button>
          <span class="table-pagination-info px-2">Página {{ page }} de {{ data.total_pages || 1 }}</span>
          <button :disabled="page >= (data.total_pages || 1)" class="btn-custom btn-custom-primary btn-custom-sm" @click="page = Math.min(data.total_pages || 1, page + 1)">Siguiente</button>
        </div>
      </div>
    </template>
  </div>
</template>
