<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { clipService, exportService } from '@/api/services'
import type { ClipListResponse, ClipSortBy } from '@/types/api'
import { ApiError } from '@/types/api'
import ExportDropdown from '@/components/ExportDropdown.vue'
import type { ExportFormat } from '@/components/ExportDropdown.vue'

type ViewMode = 'grid' | 'list'

const q = ref('')
const debouncedQ = ref('')
const minScore = ref('')
const sortBy = ref<ClipSortBy>('created_at_desc')
const page = ref(1)
const limit = 10
const viewMode = ref<ViewMode>('grid')

const data = ref<ClipListResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const exporting = ref<ExportFormat | null>(null)
const exportError = ref<string | null>(null)

async function handleExport(format: ExportFormat) {
  exporting.value = format
  exportError.value = null
  try {
    await exportService.exportClips(format)
  } catch (e: unknown) {
    exportError.value = e instanceof Error ? e.message : 'Error al exportar'
  } finally {
    exporting.value = null
  }
}

let debounceTimer: number | undefined
watch(q, (v) => {
  window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => { debouncedQ.value = v }, 350)
})

watch([debouncedQ, minScore, sortBy], () => {
  page.value = 1
})

function scoreBadge(score: number | null) {
  if (score === null || score === undefined) return 'bg-gray-700 text-gray-300 border-gray-600'
  if (score >= 70) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (score >= 40) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  return 'bg-red-500/15 text-red-300 border-red-500/30'
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
}
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-white">
    <div class="max-w-6xl mx-auto px-4 py-6 sm:py-8">
      <div class="mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">Biblioteca de Clips</h1>
          <p class="text-sm text-gray-400 mt-2">Explora, busca y gestiona todos tus clips generados con filtros y paginación.</p>
        </div>
        <ExportDropdown :loading-format="exporting" :disabled="loading || !data || data.items.length === 0" @export="handleExport" />
      </div>
      <div v-if="exportError" role="alert" class="mb-4 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3">
        <p class="text-sm text-red-300">{{ exportError }}</p>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-4 sm:p-5 mb-6">
        <div class="flex flex-col gap-4">
          <div class="flex flex-col lg:flex-row gap-3">
            <div class="relative flex-1">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
              <input
                v-model="q"
                type="text"
                placeholder="Buscar por título o transcripción..."
                class="w-full rounded-xl bg-gray-800 border border-gray-700 pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition"
              />
            </div>
            <div class="flex flex-col sm:flex-row gap-3">
              <select v-model="minScore" class="rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                <option value="">Todos los scores</option>
                <option value="70">+70 Alto</option>
                <option value="40">+40 Medio</option>
              </select>
              <select v-model="sortBy" class="rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                <option value="created_at_desc">Más recientes</option>
                <option value="created_at_asc">Más antiguos</option>
                <option value="score_desc">Mayor score</option>
                <option value="score_asc">Menor score</option>
              </select>
              <div class="flex rounded-xl bg-gray-800 border border-gray-700 p-1">
                <button type="button" class="px-3 py-1.5 rounded-lg text-sm font-medium transition" :class="viewMode === 'grid' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white'" @click="viewMode = 'grid'">⊞ Grid</button>
                <button type="button" class="px-3 py-1.5 rounded-lg text-sm font-medium transition" :class="viewMode === 'list' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white'" @click="viewMode = 'list'">☰ Lista</button>
              </div>
            </div>
          </div>
          <div v-if="hasFilters()" class="flex items-center gap-2">
            <span class="text-xs text-gray-500">Filtros activos</span>
            <button class="text-xs font-medium text-violet-400 hover:text-violet-300 border border-violet-500/30 hover:border-violet-500/50 rounded-full px-3 py-1 transition" @click="resetFilters">Resetear filtros</button>
          </div>
        </div>
      </div>

      <!-- Skeletons -->
      <div v-if="loading" :class="viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'">
        <div v-for="i in 6" :key="i" class="rounded-2xl bg-gray-900 border border-gray-800 p-5 animate-pulse">
          <div class="h-4 bg-gray-800 rounded w-3/4 mb-3" />
          <div class="h-3 bg-gray-800 rounded w-1/2 mb-4" />
          <div class="h-10 bg-gray-800 rounded mb-3" />
          <div class="h-3 bg-gray-800 rounded w-1/3" />
        </div>
      </div>

      <div v-else-if="error" role="alert" class="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-center">
        <p class="text-sm text-red-300">{{ error }}</p>
        <button class="mt-4 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-xl px-4 py-2 transition" @click="fetchClips">Reintentar</button>
      </div>

      <div v-else-if="data && data.items.length === 0" class="rounded-2xl bg-gray-900 border border-dashed border-gray-700 p-10 text-center">
        <div class="h-12 w-12 rounded-full bg-gray-800 flex items-center justify-center text-xl mx-auto">🎬</div>
        <p class="text-sm font-medium text-gray-200 mt-4">No hay clips que coincidan</p>
        <p class="text-xs text-gray-500 mt-1">Prueba ajustando la búsqueda, el filtro de score o el ordenamiento.</p>
        <button v-if="hasFilters()" class="mt-5 inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium py-2.5 px-5 transition" @click="resetFilters">Limpiar filtros</button>
      </div>

      <template v-else-if="data && data.items.length > 0">
        <div v-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="clip in data.items" :key="clip.id" class="rounded-2xl bg-gray-900 border border-gray-800 p-5 flex flex-col gap-3 hover:border-gray-700 transition">
            <div class="flex items-start justify-between gap-2">
              <h3 class="text-sm font-semibold text-white line-clamp-2 flex-1">{{ clip.title || 'Clip sin título' }}</h3>
              <span class="shrink-0 inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold" :class="scoreBadge(clip.score)">{{ formatScore(clip.score) }}</span>
            </div>
            <p class="text-xs font-mono text-gray-400 bg-gray-800/60 rounded-lg px-2.5 py-1.5 border border-gray-800">{{ formatRange(clip.start_time, clip.end_time) }} · {{ new Date(clip.created_at).toLocaleDateString() }}</p>
            <p v-if="clip.transcript" class="text-sm text-gray-300 line-clamp-3 leading-relaxed bg-gray-800/40 rounded-lg px-3 py-2">{{ clip.transcript }}</p>
            <p v-else class="text-xs text-gray-500 italic">Sin transcripción disponible</p>
          </div>
        </div>

        <div v-else class="rounded-2xl bg-gray-900 border border-gray-800 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-gray-800/50 text-xs text-gray-400 uppercase">
                <tr>
                  <th class="text-left px-4 py-3 font-medium">Título</th>
                  <th class="text-left px-4 py-3 font-medium">Score</th>
                  <th class="text-left px-4 py-3 font-medium">Inicio - Fin</th>
                  <th class="text-left px-4 py-3 font-medium">Fecha</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-800">
                <tr v-for="clip in data.items" :key="clip.id" class="hover:bg-gray-800/30 transition">
                  <td class="px-4 py-3">
                    <p class="font-medium text-white line-clamp-1">{{ clip.title || 'Sin título' }}</p>
                    <p v-if="clip.transcript" class="text-xs text-gray-400 line-clamp-1 mt-1">{{ clip.transcript }}</p>
                  </td>
                  <td class="px-4 py-3"><span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold" :class="scoreBadge(clip.score)">{{ formatScore(clip.score) }}</span></td>
                  <td class="px-4 py-3 font-mono text-xs text-gray-400">{{ formatRange(clip.start_time, clip.end_time) }}</td>
                  <td class="px-4 py-3 text-xs text-gray-400">{{ new Date(clip.created_at).toLocaleDateString() }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="flex flex-col sm:flex-row items-center justify-between gap-3 mt-6 bg-gray-900 border border-gray-800 rounded-2xl px-4 py-3">
          <p class="text-xs text-gray-400">Mostrando <span class="text-white font-medium">{{ data.items.length }}</span> de <span class="text-white font-medium">{{ data.total }}</span> clips · Página {{ data.page }} de {{ data.total_pages || 1 }}</p>
          <div class="flex items-center gap-2">
            <button :disabled="page <= 1" class="px-4 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm font-medium text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-700 transition" @click="page = Math.max(1, page - 1)">Anterior</button>
            <span class="text-xs text-gray-400 px-2">Página {{ page }} de {{ data.total_pages || 1 }}</span>
            <button :disabled="page >= (data.total_pages || 1)" class="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium transition" @click="page = Math.min(data.total_pages || 1, page + 1)">Siguiente</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
