import { ref, watch, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clipService } from '@/api/services'
import type { ClipListResponse, ClipSortBy, ClipListItem, PublishPlatform } from '@/types/api'
import { ApiError } from '@/types/api'
import { usePublishStream } from '@/composables/usePublishStream'

export function useClipLibrary() {

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
  await clipService.downloadClip(clip)
}

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
  publishing.value = clipId
  activePublishId.value = clipId
  try {
    const res = await clipService.publishClip(clipId, {
      platform: plat,
      caption: cap || undefined,
      webhook_override_url: plat === 'webhook' && wh ? wh : undefined,
    })
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

watch([debouncedQ, minScore, sortBy], () => { page.value = 1 })

return {
  API_BASE_URL,
  RAW,
  activePublishId,
  caption,
  data,
  debouncedQ,
  error,
  fetchClips,
  formatDuration,
  formatRange,
  formatScore,
  getVideoSrc,
  handleDownload,
  handleToggle,
  hasFilters,
  limit,
  loading,
  minScore,
  openPublish,
  page,
  platform,
  previewClip,
  publishBadge,
  publishClip,
  publishing,
  q,
  rerendering,
  resetFilters,
  route,
  routeJobId,
  routeQ,
  router,
  scoreBadge,
  sortBy,
  submitPublish,
  toast,
  viewMode,
  webhookUrl,
  sseStatus,
  sseUrl,
  ssePublishing,
}
}
