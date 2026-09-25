<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clipService } from '@/api/services'
import type { ClipListResponse, ClipSortBy, ClipListItem, PublishPlatform } from '@/types/api'
import { ApiError } from '@/types/api'
import { usePublishStream } from '@/composables/usePublishStream'

type ViewMode = 'grid' | 'list'

const route = useRoute()
const router = useRouter()
const routeQ = computed(() => (route.query.q as string) ?? '')
const routeJobId = computed(() => (route.query.job_id as string) ?? '')
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

const publishClip = ref<ClipListItem | null>(null)
const platform = ref<PublishPlatform>('tiktok')
const caption = ref('')
const webhookUrl = ref('')
const publishing = ref<string | null>(null)
const toast = ref<string | null>(null)
const rerendering = ref<string | null>(null)
const previewClip = ref<ClipListItem | null>(null)
const activePublishId = ref<string | null>(null)
const { status: sseStatus, socialPostUrl: sseUrl, isPublishing: ssePublishing } = usePublishStream(activePublishId)

const RAW = (import.meta.env.VITE_API_URL as string | undefined ?? '').trim()
const API_BASE_URL = (RAW || 'http://localhost:8000').replace(/\/$/, '')
function getVideoSrc(clip: ClipListItem): string {
  const bust = clip.updated_at ? `?t=${new Date(clip.updated_at as unknown as string).getTime()}` : `?t=${Date.now()}`
  if (clip.stream_url) {
    const base = clip.stream_url.startsWith('http') ? clip.stream_url : `${API_BASE_URL}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}`
    return `${base}${base.includes('?') ? '&' : '?'}t=${bust.slice(1)}`
  }
  return `${API_BASE_URL}/clips/${clip.id}/descarga${bust}`
}
async function handleDownload(clip: ClipListItem) {
  const token = (() => { try { return localStorage.getItem('clipsai_token') } catch { return null } })()
  const bust = `t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
  const url = `${API_BASE_URL}/clips/${clip.id}/descarga${token ? `?token=${encodeURIComponent(token)}&${bust}` : `?${bust}`}`
  try {
    const headers: Record<string, string> = { 'ngrok-skip-browser-warning': 'true' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(url, { headers, credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition')
    let filename = `${clip.title || clip.id}.mp4`
    if (cd) {
      const m = cd.match(/filename="?([^"]+)"?/)
      if (m) filename = m[1]
    }
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
  } catch {
    window.open(`${API_BASE_URL}/clips/${clip.id}/descarga`, '_blank')
  }
}

watch(routeQ, (v) => {
  if (v !== q.value) {
    q.value = v
    debouncedQ.value = v
  }
})

watch(routeJobId, () => { page.value = 1 })

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

watch(() => sseStatus.value, (term) => {
  if (!activePublishId.value || !term) return
  const upper = term.toUpperCase()
  if (upper === 'PUBLISHED') {
    if (data.value) data.value.items = data.value.items.map((c) => c.id === activePublishId.value ? { ...c, status: 'PUBLISHED', social_post_url: sseUrl.value || c.social_post_url } : c)
    toast.value = `Publicado ✅ ${sseUrl.value ?? ''}`.trim()
    publishing.value = null
    activePublishId.value = null
    setTimeout(() => (toast.value = null), 4000)
    fetchClips()
  } else if (upper === 'FAILED') {
    if (data.value) data.value.items = data.value.items.map((c) => c.id === activePublishId.value ? { ...c, status: 'FAILED' } : c)
    toast.value = 'Error al publicar — FAILED'
    publishing.value = null
    activePublishId.value = null
    setTimeout(() => (toast.value = null), 4000)
  } else if (upper === 'PUBLISHING') {
    if (data.value) data.value.items = data.value.items.map((c) => c.id === activePublishId.value ? { ...c, status: 'PUBLISHING' } : c)
  }
})

function scoreBadge(score: number | null) {
  if (score === null || score === undefined) return 'score-badge-neon low'
  if (score >= 70) return 'score-badge-neon high'
  if (score >= 40) return 'score-badge-neon mid'
  return 'score-badge-neon low'
}

function publishBadge(status?: string | null) {
  if (status === 'PUBLISHING' || status === 'publishing') return { label: 'PUBLISHING', cls: 'bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse' }
  if (status === 'PUBLISHED' || status === 'published') return { label: 'PUBLISHED', cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' }
  return null
}

function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—'
  return score.toFixed(1)
}

function formatRange(start: number, end: number): string {
  return `${start.toFixed(1)}s — ${end.toFixed(1)}s`
}

function formatDuration(item: ClipListItem): string {
  const dur = item.duration ?? (item.end_time - item.start_time)
  const m = Math.floor(dur / 60)
  const s = Math.floor(dur % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
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
      job_id: (route.query.job_id as string) || undefined,
    })
    if (data.value) {
      data.value.items = [...data.value.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    }
  } catch (err: unknown) {
    if (err instanceof ApiError) error.value = err.detail
    else if (err instanceof Error) error.value = err.message
    else error.value = 'Error al cargar clips'
  } finally {
    loading.value = false
  }
}

watch([debouncedQ, minScore, sortBy, page, routeJobId], fetchClips)
onMounted(fetchClips)

const hasFilters = () => debouncedQ.value !== '' || minScore.value !== '' || sortBy.value !== 'created_at_desc' || !!routeJobId.value

function resetFilters() {
  q.value = ''
  debouncedQ.value = ''
  minScore.value = ''
  sortBy.value = 'created_at_desc'
  page.value = 1
  const query: Record<string, string> = { ...(route.query as Record<string, string>) }
  delete query.q
  delete query.job_id
  router.replace({ path: route.path, query })
}

function openPublish(clip: ClipListItem) {
  publishClip.value = clip
  platform.value = 'tiktok'
  caption.value = clip.title ? `${clip.title} #viral` : '¡Increíble momento! #RiverPlate'
  webhookUrl.value = ''
}

async function submitPublish() {
  if (!publishClip.value) return
  const clipId = publishClip.value.id
  const plat = platform.value
  const cap = caption.value
  const wh = webhookUrl.value
  console.log('[publish] submit', { clipId, plat, cap })
  publishing.value = clipId
  activePublishId.value = clipId
  try {
    const res = await clipService.publishClip(clipId, {
      platform: plat,
      caption: cap || undefined,
      webhook_override_url: plat === 'webhook' && wh ? wh : undefined,
    })
    console.log('[publish] 202', res)
    toast.value = `Publicación en ${plat} encolada — PUBLISHING`
    publishClip.value = null
    if (data.value) {
      data.value.items = data.value.items.map((c) => c.id === clipId ? { ...c, status: 'PUBLISHING', published_platform: plat } : c)
    }
    setTimeout(() => (toast.value = null), 4000)
  } catch (e: unknown) {
    console.error('[publish] error', e)
    toast.value = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error al publicar'
    publishing.value = null
    activePublishId.value = null
    setTimeout(() => (toast.value = null), 4000)
  }
}

async function handleToggle(clip: ClipListItem, enable_ass: boolean, enable_hook: boolean) {
  rerendering.value = clip.id
  try {
    await clipService.reRenderClip(clip.id, { enable_ass, enable_hook })
    toast.value = 'Re-render encolado — procesando clip...'
    setTimeout(() => fetchClips(), 1200)
    setTimeout(() => (toast.value = null), 4000)
  } catch (e: unknown) {
    toast.value = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error en re-render'
    setTimeout(() => (toast.value = null), 4000)
  } finally {
    rerendering.value = null
  }
}
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <div v-if="toast" class="fixed top-4 right-4 z-[9999] bg-[#121824] border border-[#B4F105]/30 text-[#F1F5F9] px-4 py-3 rounded-xl shadow-xl text-sm font-semibold">{{ toast }}</div>
    <div class="page-header" style="margin-bottom: 2rem">
      <div>
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]"><i class="bi bi-collection-play" style="font-size: 1.15rem" /></span>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]"><i class="bi bi-stars" /> Biblioteca</span>
          <span v-if="data" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border bg-[rgba(180,241,5,0.10)] text-[#B4F105] border-[rgba(180,241,5,0.22)]">{{ data.total }} clips</span>
          <span v-if="routeJobId" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-[#0B0F17] text-[#94A3B8] border border-white/10">job {{ routeJobId.slice(0,8) }}…</span>
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
        <div v-for="clip in data.items" :key="clip.id" class="clip-card relative overflow-hidden" style="margin-bottom: 0">
          <div v-if="rerendering === clip.id" class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-black/60 backdrop-blur-sm rounded-xl">
            <span class="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
            <span class="text-xs font-bold text-white">Re-renderizando clip...</span>
          </div>
          <div class="flex items-start justify-between gap-2">
            <h3 class="text-sm font-bold line-clamp-2 flex-1 cursor-pointer hover:text-[#B4F105]" style="color: #F1F5F9" @click="previewClip = clip">{{ clip.title || 'Clip sin título' }}</h3>
            <span :class="scoreBadge(clip.score)">Viral Score: {{ formatScore(clip.score) }}/100</span>
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            <p class="text-xs font-mono px-2.5 py-1.5 rounded-full border inline-flex items-center gap-1.5" style="color: #94A3B8; background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.08)"><i class="bi bi-clock" style="font-size: 0.7rem" /> {{ formatRange(clip.start_time, clip.end_time) }} · {{ formatDuration(clip) }}</p>
          </div>
          <div @click="previewClip = clip" class="cursor-pointer rounded-xl overflow-hidden border border-white/5 bg-black/20 hover:border-[#B4F105]/30 transition-colors">
            <p v-if="clip.transcript" class="text-sm line-clamp-3 leading-relaxed px-3 py-2.5" style="color: #CBD5E1">{{ clip.transcript }}</p>
            <p v-else class="text-xs italic px-3 py-2.5" style="color: #64748B">Sin transcripción disponible</p>
            <div class="flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-bold text-[#94A3B8] border-t border-white/5 mt-1"><i class="bi bi-play-circle" /> Vista previa 9:16</div>
          </div>
          <div class="flex items-center gap-3 p-2.5 rounded-xl bg-[#0B0F17] border border-white/10">
            <label class="flex items-center gap-2 flex-1 cursor-pointer">
              <span class="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i class="bi bi-badge-cc" /> Subtítulos ASS</span>
              <button type="button" role="switch" :aria-checked="!!clip.has_ass" :disabled="rerendering===clip.id || publishing===clip.id" @click="handleToggle(clip, !clip.has_ass, !!clip.has_hook)" :class="`ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition ${clip.has_ass ? 'bg-[#B4F105]' : 'bg-white/10'} ${rerendering===clip.id ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`">
                <span :class="`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${clip.has_ass ? 'translate-x-5' : 'translate-x-1'}`" />
              </button>
            </label>
            <span class="h-6 w-px bg-white/10" />
            <label class="flex items-center gap-2 flex-1 cursor-pointer">
              <span class="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i class="bi bi-lightning" /> Hook Teaser</span>
              <button type="button" role="switch" :aria-checked="!!clip.has_hook" :disabled="rerendering===clip.id || publishing===clip.id" @click="handleToggle(clip, !!clip.has_ass, !clip.has_hook)" :class="`ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition ${clip.has_hook ? 'bg-[#B4F105]' : 'bg-white/10'} ${rerendering===clip.id ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`">
                <span :class="`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${clip.has_hook ? 'translate-x-5' : 'translate-x-1'}`" />
              </button>
            </label>
          </div>
          <div class="flex items-center gap-2 flex-wrap pt-1">
            <span v-if="publishBadge(clip.status)" :class="`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border ${publishBadge(clip.status)!.cls}`">
              <span v-if="publishBadge(clip.status)!.label==='PUBLISHING'" class="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />{{ publishBadge(clip.status)!.label }}
            </span>
            <span v-else-if="activePublishId===clip.id && sseStatus==='PUBLISHED'" class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span>
            <template v-else><span class="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.5)]" /><span class="text-[11px] font-semibold tracking-wide uppercase" style="color: #94A3B8">Listo para publicar</span></template>
            <a v-if="clip.social_post_url || (activePublishId===clip.id && sseUrl)" :href="(clip.social_post_url || sseUrl) || '#'" target="_blank" class="text-xs font-bold text-[#B4F105] hover:underline inline-flex items-center gap-1"><i class="bi bi-box-arrow-up-right" /> Ver post</a>
          </div>
          <div class="grid grid-cols-3 gap-2 mt-2">
            <button @click="previewClip = clip" class="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1"><i class="bi bi-eye" /> Ver</button>
            <button @click="handleDownload(clip)" class="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1"><i class="bi bi-download" /> Descargar MP4</button>
            <button @click="openPublish(clip)" :disabled="rerendering===clip.id || publishing===clip.id || (ssePublishing && activePublishId===clip.id)" class="btn-custom btn-custom-primary !py-2 text-xs font-bold disabled:opacity-50 flex items-center justify-center gap-1">
              <span v-if="publishing===clip.id || (ssePublishing && activePublishId===clip.id)" class="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" />{{ (publishing===clip.id || (ssePublishing && activePublishId===clip.id)) ? 'Publicando...' : (clip.status==='PUBLISHED' || sseStatus==='PUBLISHED') ? 'Publicado ✅' : 'Publicar' }}
            </button>
          </div>
        </div>
      </div>

      <div v-else class="table-card-custom">
        <div class="table-responsive" style="overflow-x: auto">
          <table class="table-custom">
            <thead>
              <tr>
                <th>Título</th>
                <th>Viral Score</th>
                <th>Duración</th>
                <th>ASS / Hook</th>
                <th>Estado</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="clip in data.items" :key="clip.id" :class="rerendering===clip.id ? 'opacity-60' : ''">
                <td>
                  <p class="font-bold line-clamp-1 cursor-pointer hover:text-[#B4F105]" style="color: var(--text-main)" @click="previewClip = clip">{{ clip.title || 'Sin título' }}</p>
                  <p v-if="clip.transcript" class="text-xs line-clamp-1 mt-1" style="color: var(--text-muted-green)">{{ clip.transcript }}</p>
                </td>
                <td><span :class="scoreBadge(clip.score)">Viral Score: {{ formatScore(clip.score) }}/100</span></td>
                <td class="font-mono text-xs" style="color: var(--text-muted-green)">{{ formatDuration(clip) }}<br /><span class="text-[11px] text-[#64748B]">{{ formatRange(clip.start_time, clip.end_time) }}</span></td>
                <td>
                  <div class="flex items-center gap-2">
                    <label class="flex items-center gap-1 text-[11px]"><input type="checkbox" :checked="!!clip.has_ass" :disabled="rerendering===clip.id" @change="handleToggle(clip, ($event.target as HTMLInputElement).checked, !!clip.has_hook)" class="accent-[#B4F105] disabled:opacity-50" /> ASS</label>
                    <label class="flex items-center gap-1 text-[11px]"><input type="checkbox" :checked="!!clip.has_hook" :disabled="rerendering===clip.id" @change="handleToggle(clip, !!clip.has_ass, ($event.target as HTMLInputElement).checked)" class="accent-[#B4F105] disabled:opacity-50" /> Hook</label>
                    <span v-if="rerendering===clip.id" class="h-3 w-3 animate-spin rounded-full border border-white/30 border-t-[#B4F105]" />
                  </div>
                </td>
                <td>
                  <span v-if="publishing===clip.id || (ssePublishing && activePublishId===clip.id)" class="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse">Publicando...</span>
                  <span v-else-if="clip.status==='PUBLISHED' || (sseStatus==='PUBLISHED' && activePublishId===clip.id)" class="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span>
                  <span v-else-if="publishBadge(clip.status)" :class="`inline-flex px-2 py-1 rounded-full text-[11px] font-bold border ${publishBadge(clip.status)!.cls}`">{{ publishBadge(clip.status)!.label }}</span>
                  <span v-else class="text-xs text-[#94A3B8]">ready</span>
                  <a v-if="clip.social_post_url || (sseUrl && activePublishId===clip.id)" :href="(clip.social_post_url || sseUrl) || '#'" target="_blank" class="ml-2 text-xs text-[#B4F105] hover:underline">Ver</a>
                </td>
                <td>
                  <div class="flex items-center gap-1">
                    <button @click="previewClip = clip" class="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Vista previa 9:16"><i class="bi bi-eye" /></button>
                    <button @click="handleDownload(clip)" class="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Descargar MP4"><i class="bi bi-download" /></button>
                    <button @click="openPublish(clip)" :disabled="rerendering===clip.id || publishing===clip.id || (ssePublishing && activePublishId===clip.id)" class="btn-custom btn-custom-primary btn-custom-sm !text-xs disabled:opacity-50">{{ (publishing===clip.id || (ssePublishing && activePublishId===clip.id)) ? 'Publicando...' : 'Publicar' }}</button>
                  </div>
                </td>
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

    <!-- Preview 9:16 -->
    <div v-if="previewClip" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" @click="previewClip=null">
      <div class="relative w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-4 shadow-2xl flex flex-col gap-3" @click.stop>
        <div class="flex items-start justify-between gap-2">
          <div class="flex-1 min-w-0">
            <h3 class="text-sm font-extrabold text-[#F1F5F9] line-clamp-2">{{ previewClip.title || 'Clip sin título' }}</h3>
            <p class="text-xs font-mono text-[#94A3B8] mt-1">Viral Score: {{ formatScore(previewClip.score) }}/100 · {{ formatDuration(previewClip) }}</p>
          </div>
          <button @click="previewClip=null" class="h-8 w-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"><i class="bi bi-x-lg" /></button>
        </div>
        <div class="flex justify-center bg-black rounded-xl overflow-hidden p-2">
          <video :key="previewClip.id" controls autoplay playsinline :src="getVideoSrc(previewClip)" class="max-h-[80vh] w-auto mx-auto rounded-lg shadow-2xl" style="aspect-ratio: 9/16; max-width: 360px; width: 100%; object-fit: contain; background: black" />
        </div>
        <p v-if="previewClip.transcript" class="text-xs leading-relaxed px-2 py-2 rounded-lg bg-[#0B0F17] border border-white/10 text-[#94A3B8] line-clamp-3">{{ previewClip.transcript }}</p>
        <div class="grid grid-cols-2 gap-2">
          <button @click="handleDownload(previewClip!)" class="btn-custom btn-custom-light !py-2.5 text-xs font-bold flex items-center justify-center gap-1"><i class="bi bi-download" /> Descargar MP4</button>
          <button @click="previewClip=null; openPublish(previewClip!)" class="btn-custom btn-custom-primary !py-2.5 text-xs font-bold flex items-center justify-center gap-1"><i class="bi bi-send" /> Publicar</button>
        </div>
        <a v-if="previewClip.social_post_url || (sseUrl && activePublishId===previewClip.id)" :href="(previewClip.social_post_url || sseUrl) || '#'" target="_blank" class="text-center text-xs font-bold text-[#B4F105] hover:underline">Ver publicación → {{ previewClip.social_post_url || sseUrl }}</a>
      </div>
    </div>

    <div v-if="publishClip" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" @click="publishClip=null">
      <div class="w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-6 shadow-2xl" @click.stop>
        <h3 class="text-lg font-extrabold text-[#F1F5F9] mb-1">Publicar clip</h3>
        <p class="text-xs text-[#94A3B8] mb-4 line-clamp-2">{{ publishClip.title || 'Clip sin título' }}</p>
        <label class="block text-xs font-bold text-[#CBD5E1] mb-1">Plataforma</label>
        <div class="grid grid-cols-2 gap-2 mb-3">
          <button v-for="p in (['tiktok','instagram','youtube','webhook'] as PublishPlatform[])" :key="p" type="button" @click="platform=p" :class="`px-3 py-2.5 rounded-xl text-xs font-bold border capitalize transition ${platform===p ? 'bg-[#B4F105] text-[#080C14] border-[#B4F105] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'bg-[#0B0F17] text-[#94A3B8] border-white/10 hover:border-white/20'}`">
            {{ p==='youtube' ? 'YouTube Shorts' : p==='instagram' ? 'Instagram Reels' : p }}
          </button>
        </div>
        <label class="block text-xs font-bold text-[#CBD5E1] mb-1">Caption</label>
        <textarea v-model="caption" rows="3" maxlength="500" placeholder="¡Increíble momento de River! #RiverPlate" class="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105] resize-none" />
        <p class="text-[11px] text-[#64748B] text-right mt-1">{{ caption.length }}/500</p>
        <template v-if="platform==='webhook'">
          <label class="block text-xs font-bold text-[#CBD5E1] mt-3 mb-1">Webhook URL (opcional, override)</label>
          <input v-model="webhookUrl" placeholder="https://hooks.example.com/publish" class="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105]" />
        </template>
        <div class="flex gap-2 mt-5">
          <button @click="publishClip=null" class="flex-1 btn-custom btn-custom-light">Cancelar</button>
          <button @click="submitPublish" :disabled="publishing!==null || (ssePublishing && activePublishId===publishClip?.id)" class="flex-1 btn-custom btn-custom-primary font-bold disabled:opacity-50 flex items-center justify-center gap-1"><span v-if="publishing || (ssePublishing && activePublishId===publishClip?.id)" class="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" />{{ publishing || (ssePublishing && activePublishId===publishClip?.id) ? 'Publicando...' : 'Publicar ahora' }}</button>
        </div>
        <p v-if="ssePublishing && activePublishId===publishClip?.id" class="text-[11px] text-amber-400 mt-2 flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> Escuchando SSE...</p>
      </div>
    </div>
  </div>
</template>
