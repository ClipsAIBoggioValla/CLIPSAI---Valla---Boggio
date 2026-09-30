import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { clipService } from '@/services/api'
import type { ClipListItem, ClipListResponse, ClipSortBy, PublishPlatform } from '@/types/api'
import { ApiError } from '@/types/api'
import { usePublishSSE } from '@/hooks/usePublishSSE'
import { TOKEN_KEY } from '@/lib/apiClient'

type ViewMode = 'grid' | 'list'

const RAW_BASE: string =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()
const API_BASE_URL = (RAW_BASE || 'http://localhost:8000').replace(/\/$/, '')

function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—'
  return score.toFixed(1)
}

function formatDuration(item: ClipListItem): string {
  const dur = item.duration ?? (item.end_time - item.start_time)
  const m = Math.floor(dur / 60)
  const s = Math.floor(dur % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatTimeRange(item: ClipListItem): string {
  return `${item.start_time.toFixed(1)}s — ${item.end_time.toFixed(1)}s`
}

function scoreBadgeClass(score: number | null): string {
  if (score === null || score === undefined) return 'score-badge-neon low'
  if (score >= 70) return 'score-badge-neon high'
  if (score >= 40) return 'score-badge-neon mid'
  return 'score-badge-neon low'
}

function publishBadge(status?: string | null) {
  if (status === 'PUBLISHING' || status === 'publishing') return { label: 'PUBLISHING', cls: 'bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse' }
  if (status === 'PUBLISHED' || status === 'published') return { label: 'PUBLISHED', cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' }
  if (status === 'FAILED' || status === 'failed') return { label: 'FAILED', cls: 'bg-red-500/20 text-red-400 border-red-500/30' }
  return null
}

function getVideoSrc(clip: ClipListItem): string {
  const bust = clip.updated_at ? `?t=${new Date(clip.updated_at).getTime()}` : `?t=${Date.now()}`
  // FIX Parte 1: cache busting para romper caché tras re-render (Issue #35)
  if (clip.stream_url) {
    const base = clip.stream_url.startsWith('http') ? clip.stream_url : `${API_BASE_URL}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}`
    return `${base}${base.includes('?') ? '&' : '?'}t=${bust.slice(1)}`
  }
  return `${API_BASE_URL}/clips/${clip.id}/descarga${bust}`
}

export default function ClipLibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlQ = searchParams.get('q') ?? ''
  const jobId = searchParams.get('job_id') ?? undefined
  const [q, setQ] = useState(urlQ)
  const [debouncedQ, setDebouncedQ] = useState(urlQ)
  const [minScore, setMinScore] = useState<string>('')
  const [sortBy, setSortBy] = useState<ClipSortBy>('created_at_desc')
  const [page, setPage] = useState(1)
  const [limit] = useState(10)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [data, setData] = useState<ClipListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [publishClip, setPublishClip] = useState<ClipListItem | null>(null)
  const [platform, setPlatform] = useState<PublishPlatform>('tiktok')
  const [caption, setCaption] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [publishing, setPublishing] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [rerendering, setRerendering] = useState<string | null>(null)
  const [previewClip, setPreviewClip] = useState<ClipListItem | null>(null)
  const [activePublishId, setActivePublishId] = useState<string | null>(null)
  const { status: sseStatus, socialPostUrl: sseUrl, isPublishing: ssePublishing } = usePublishSSE(activePublishId)

  useEffect(() => {
    if (urlQ !== q) setQ(urlQ)
  }, [urlQ])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 350)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    setPage(1)
  }, [debouncedQ, minScore, sortBy, jobId])

  const fetchClips = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await clipService.getClips({
        q: debouncedQ || undefined,
        min_score: minScore ? Number(minScore) : undefined,
        sort_by: sortBy,
        page,
        limit,
        job_id: jobId,
      })
      const sortedItems = [...res.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      setData({ ...res, items: sortedItems })
    } catch (err: unknown) {
      if (err instanceof ApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError('Error al cargar clips')
    } finally {
      setLoading(false)
    }
  }, [debouncedQ, minScore, sortBy, page, limit, jobId])

  useEffect(() => {
    fetchClips()
  }, [fetchClips])

  // Sincronizar SSE con lista
  useEffect(() => {
    if (!activePublishId || !sseStatus) return
    const term = sseStatus.toUpperCase()
    if (term === 'PUBLISHED') {
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === activePublishId ? { ...c, status: 'PUBLISHED', social_post_url: sseUrl || c.social_post_url, published_platform: c.published_platform } : c) } : prev)
      setToast(`Publicado \u2705 ${sseUrl ? sseUrl : ''}`.trim())
      setPublishing(null)
      setActivePublishId(null)
      setTimeout(() => setToast(null), 4000)
      fetchClips()
    } else if (term === 'FAILED') {
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === activePublishId ? { ...c, status: 'FAILED' } : c) } : prev)
      setToast('Error al publicar — FAILED')
      setPublishing(null)
      setActivePublishId(null)
      setTimeout(() => setToast(null), 4000)
    } else if (term === 'PUBLISHING') {
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === activePublishId ? { ...c, status: 'PUBLISHING' } : c) } : prev)
    }
  }, [sseStatus, sseUrl, activePublishId, fetchClips])

  // Si SSE indica publishing pero el clip ya no está en lista, limpiar
  useEffect(() => {
    if (ssePublishing && activePublishId) {
      setPublishing(activePublishId)
    }
  }, [ssePublishing, activePublishId])

  const hasFilters = debouncedQ !== '' || minScore !== '' || sortBy !== 'created_at_desc' || !!jobId
  const totalPages = data?.total_pages ?? 0

  function resetFilters() {
    setQ('')
    setDebouncedQ('')
    setMinScore('')
    setSortBy('created_at_desc')
    setPage(1)
    const next = new URLSearchParams(searchParams)
    next.delete('q')
    next.delete('job_id')
    setSearchParams(next, { replace: true })
  }

  function openPublish(clip: ClipListItem) {
    setPublishClip(clip)
    setPlatform('tiktok')
    setCaption(clip.title ? `${clip.title} #viral` : '¡Increíble momento! #RiverPlate')
    setWebhookUrl('')
  }

  async function submitPublish() {
    if (!publishClip) return
    const clipId = publishClip.id
    const plat = platform
    const cap = caption
    const wh = webhookUrl
    console.log('[publish] submit', { clipId, plat, cap })
    setPublishing(clipId)
    try {
      const res = await clipService.publishClip(clipId, {
        platform: plat,
        caption: cap || undefined,
        webhook_override_url: plat === 'webhook' && wh ? wh : undefined,
      })
      console.log('[publish] 202', res)
      setActivePublishId(clipId)
      setToast(`Publicación en ${plat} encolada — PUBLISHING`)
      setPublishClip(null)
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === clipId ? { ...c, status: 'PUBLISHING', published_platform: plat } : c) } : prev)
      // No fetch inmediato, SSE actualizará
      setTimeout(() => setToast(null), 4000)
    } catch (e: unknown) {
      console.error('[publish] error', e)
      const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error al publicar'
      setToast(msg)
      setPublishing(null)
      setActivePublishId(null)
      setTimeout(() => setToast(null), 4000)
    }
  }

  async function handleToggle(clip: ClipListItem, enable_ass: boolean, enable_hook: boolean) {
    setRerendering(clip.id)
    try {
      await clipService.reRenderClip(clip.id, { enable_ass, enable_hook })
      setToast('Re-render encolado — procesando clip...')
      setTimeout(() => fetchClips(), 1200)
      setTimeout(() => setToast(null), 4000)
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error en re-render'
      setToast(msg)
      setTimeout(() => setToast(null), 4000)
    } finally {
      setRerendering(null)
    }
  }

  async function handleDownload(clip: ClipListItem) {
    const token = (() => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } })()
    const bust = `t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
    const url = `${API_BASE_URL}/clips/${clip.id}/descarga${token ? `?token=${encodeURIComponent(token)}&${bust}` : `?${bust}`}`
    try {
      // Intentar fetch con auth para descarga directa
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
      // Fallback: abrir en nueva pestaña
      const fallback = clipService.downloadUrl(clip.id)
      window.open(fallback, '_blank')
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      {toast && <div className="fixed top-4 right-4 z-[9999] bg-[#121824] border border-[#B4F105]/30 text-[#F1F5F9] px-4 py-3 rounded-xl shadow-xl text-sm font-semibold">{toast}</div>}
      <div className="page-header" style={{ marginBottom: '2rem' }}>
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]">
              <i className="bi bi-collection-play" style={{ fontSize: '1.15rem' }} />
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]">
              <i className="bi bi-stars" /> Biblioteca
            </span>
            {data && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border bg-[rgba(180,241,5,0.10)] text-[#B4F105] border-[rgba(180,241,5,0.22)]">
                {data.total} clips
              </span>
            )}
            {jobId && <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-[#0B0F17] text-[#94A3B8] border border-white/10">job {jobId.slice(0,8)}…</span>}
          </div>
          <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.25rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>
            Biblioteca de Clips
          </h1>
          <p className="page-subtitle" style={{ marginBottom: 0, marginTop: '0.7rem', fontSize: '0.92rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6, maxWidth: '640px' }}>
            Explora, busca y gestiona todos tus clips generados con filtros inteligentes y paginación fluida.
          </p>
        </div>
      </div>

      <div className="flex flex-col md:flex-row items-center justify-between gap-4 p-3 bg-[#121824] rounded-xl border border-white/10" style={{ marginBottom: '1rem', minHeight: '56px' }}>
        <div className="relative flex-1 max-w-md w-full">
          <i className="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" style={{ fontSize: '0.9rem' }} />
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por título o transcripción..."
            className="w-full pl-9 pr-4 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:border-[#B4F105] transition-colors"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <select value={minScore} onChange={(e) => setMinScore(e.target.value)} className="bg-[#0B0F17] text-xs text-white border border-white/10 rounded-lg px-3 py-2 cursor-pointer focus:outline-none hover:border-white/20 transition-colors">
            <option value="">Todos los scores</option>
            <option value="70">+70 Alto</option>
            <option value="40">+40 Medio</option>
          </select>

          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as ClipSortBy)} className="bg-[#0B0F17] text-xs text-white border border-white/10 rounded-lg px-3 py-2 cursor-pointer focus:outline-none hover:border-white/20 transition-colors">
            <option value="created_at_desc">Más recientes</option>
            <option value="created_at_asc">Más antiguos</option>
            <option value="score_desc">Mayor score</option>
            <option value="score_asc">Menor score</option>
          </select>

          <div className="py-1 px-1 bg-[#0B0F17] border border-white/10 rounded-lg flex items-center gap-1">
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition ${viewMode === 'grid' ? 'bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'text-[#94A3B8] hover:text-white'}`}
              aria-label="Vista de tarjetas"
            >
              ⊞ Grid
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition ${viewMode === 'list' ? 'bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'text-[#94A3B8] hover:text-white'}`}
              aria-label="Vista de tabla"
            >
              ☰ Lista
            </button>
          </div>
        </div>
      </div>

      {hasFilters && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-bold text-[#94A3B8]">Filtros activos</span>
          <button onClick={resetFilters} className="btn-custom btn-custom-light btn-custom-sm !py-1 !text-xs">
            Resetear filtros
          </button>
        </div>
      )}

      {loading && (
        <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card-spark animate-pulse">
              <div className="h-4 bg-[rgba(255,255,255,0.06)] rounded w-3/4 mb-3" />
              <div className="h-3 bg-[rgba(255,255,255,0.04)] rounded w-1/2 mb-4" />
              <div className="h-10 bg-[rgba(255,255,255,0.04)] rounded mb-3" />
              <div className="h-3 bg-[rgba(255,255,255,0.04)] rounded w-1/3" />
            </div>
          ))}
        </div>
      )}

      {error && !loading && (
        <div role="alert" className="alert-custom alert-custom-danger">
          <i className="bi bi-exclamation-circle-fill alert-custom-icon" />
          <div className="alert-custom-content">{error}</div>
          <button onClick={fetchClips} className="btn-custom btn-custom-danger btn-custom-sm">
            Reintentar
          </button>
        </div>
      )}

      {!loading && !error && data && data.items.length === 0 && (
        <div className="card-spark text-center" style={{ borderStyle: 'dashed', padding: '2.5rem', borderColor: 'rgba(180,241,5,0.18)' }}>
          <div className="h-12 w-12 rounded-full flex items-center justify-center text-xl mx-auto bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.06)]">
            🎬
          </div>
          <p className="text-sm font-bold mt-4" style={{ color: '#F1F5F9' }}>
            No hay clips que coincidan
          </p>
          <p className="text-xs mt-1" style={{ color: '#94A3B8' }}>
            Prueba ajustando la búsqueda, el filtro de score o el ordenamiento.
          </p>
          {hasFilters && (
            <button onClick={resetFilters} className="btn-custom btn-custom-primary mt-5">
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      {!loading && !error && data && data.items.length > 0 && (
        <>
          {viewMode === 'grid' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.items.map((clip) => {
                const pb = publishBadge(clip.status)
                const isRerendering = rerendering === clip.id
                const isPublishing = publishing === clip.id || ssePublishing && activePublishId === clip.id
                const isBusy = isRerendering || isPublishing || clip.status === 'PUBLISHING'
                const isPublished = clip.status === 'PUBLISHED' || sseStatus === 'PUBLISHED' && activePublishId === clip.id
                return (
                  <div key={clip.id} className="clip-card relative overflow-hidden group" style={{ marginBottom: 0 }}>
                    {isRerendering && (
                      <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-black/60 backdrop-blur-sm rounded-xl">
                        <span className="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
                        <span className="text-xs font-bold text-white">Re-renderizando clip...</span>
                      </div>
                    )}
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-bold line-clamp-2 flex-1 cursor-pointer hover:text-[#B4F105] transition-colors" style={{ color: '#F1F5F9' }} onClick={() => setPreviewClip(clip)}>
                        {clip.title || 'Clip sin título'}
                      </h3>
                      <span className={scoreBadgeClass(clip.score)}>Viral Score: {formatScore(clip.score)}/100</span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-xs font-mono px-2.5 py-1.5 rounded-full border inline-flex items-center gap-1.5" style={{ color: '#94A3B8', background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}>
                        <i className="bi bi-clock" style={{ fontSize: '0.7rem' }} /> {formatTimeRange(clip)} · {formatDuration(clip)}
                      </p>
                      <span className="text-[11px] font-mono px-2 py-1 rounded-full bg-[#0B0F17] border border-white/10 text-[#CBD5E1]">{new Date(clip.created_at).toLocaleDateString()}</span>
                    </div>
                    <div onClick={() => setPreviewClip(clip)} className="cursor-pointer rounded-xl overflow-hidden border border-white/5 bg-black/20 hover:border-[#B4F105]/30 transition-colors group-hover:shadow-[0_0_12px_rgba(180,241,5,0.15)]">
                      {clip.transcript ? (
                        <p className="text-sm line-clamp-3 leading-relaxed px-3 py-2.5" style={{ color: '#CBD5E1' }}>
                          {clip.transcript}
                        </p>
                      ) : (
                        <p className="text-xs italic px-3 py-2.5" style={{ color: '#64748B' }}>
                          Sin transcripción disponible
                        </p>
                      )}
                      <div className="flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-bold text-[#94A3B8] group-hover:text-[#B4F105] border-t border-white/5 mt-1">
                        <i className="bi bi-play-circle" /> Vista previa 9:16
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[#0B0F17] border border-white/10">
                      <label className="flex items-center gap-2 flex-1 cursor-pointer">
                        <span className="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i className="bi bi-badge-cc" /> Subtítulos ASS</span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={!!clip.has_ass}
                          disabled={!!isBusy}
                          onClick={() => handleToggle(clip, !clip.has_ass, !!clip.has_hook)}
                          className={`ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition ${clip.has_ass ? 'bg-[#B4F105]' : 'bg-white/10'} ${isBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${clip.has_ass ? 'translate-x-5' : 'translate-x-1'}`} />
                        </button>
                      </label>
                      <span className="h-6 w-px bg-white/10" />
                      <label className="flex items-center gap-2 flex-1 cursor-pointer">
                        <span className="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i className="bi bi-lightning" /> Hook Teaser</span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={!!clip.has_hook}
                          disabled={!!isBusy}
                          onClick={() => handleToggle(clip, !!clip.has_ass, !clip.has_hook)}
                          className={`ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition ${clip.has_hook ? 'bg-[#B4F105]' : 'bg-white/10'} ${isBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${clip.has_hook ? 'translate-x-5' : 'translate-x-1'}`} />
                        </button>
                      </label>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap pt-1">
                      {pb ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border ${pb.cls}`}>
                          {pb.label === 'PUBLISHING' && <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />}
                          {pb.label}
                        </span>
                      ) : isPublished ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span>
                      ) : (
                        <><span className="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.5)]" /><span className="text-[11px] font-semibold tracking-wide uppercase" style={{ color: '#94A3B8' }}>Listo para publicar</span></>
                      )}
                      {(clip.social_post_url || (isPublished && sseUrl)) && (
                        <a href={clip.social_post_url || sseUrl || '#'} target="_blank" rel="noopener noreferrer" className="text-xs font-bold text-[#B4F105] hover:underline inline-flex items-center gap-1">
                          <i className="bi bi-box-arrow-up-right" /> Ver post
                        </a>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      <button type="button" onClick={() => setPreviewClip(clip)} className="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
                        <i className="bi bi-eye" /> Ver
                      </button>
                      <button type="button" onClick={() => handleDownload(clip)} className="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
                        <i className="bi bi-download" /> Descargar MP4
                      </button>
                      <button type="button" onClick={() => openPublish(clip)} disabled={!!isBusy} className="btn-custom btn-custom-primary !py-2 text-xs font-bold disabled:opacity-50 flex items-center justify-center gap-1">
                        {isPublishing ? <><span className="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" /> Publicando...</> : isPublished ? 'Publicado ✅' : 'Publicar'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="table-card-custom">
              <div className="table-responsive" style={{ overflowX: 'auto' }}>
                <table className="table-custom">
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
                    {data.items.map((clip) => {
                      const pb = publishBadge(clip.status)
                      const isRerendering = rerendering === clip.id
                      const isPublishing = publishing === clip.id || (ssePublishing && activePublishId === clip.id)
                      const isBusy = isRerendering || isPublishing
                      const isPublished = clip.status === 'PUBLISHED' || (sseStatus === 'PUBLISHED' && activePublishId === clip.id)
                      return (
                        <tr key={clip.id} className={isRerendering ? 'opacity-60' : ''}>
                          <td>
                            <p className="font-bold line-clamp-1 cursor-pointer hover:text-[#B4F105]" style={{ color: 'var(--text-main)' }} onClick={() => setPreviewClip(clip)}>
                              {clip.title || 'Sin título'}
                            </p>
                            {clip.transcript && <p className="text-xs line-clamp-1 mt-1" style={{ color: 'var(--text-muted-green)' }}>{clip.transcript}</p>}
                          </td>
                          <td>
                            <span className={scoreBadgeClass(clip.score)}>Viral Score: {formatScore(clip.score)}/100</span>
                          </td>
                          <td className="font-mono text-xs" style={{ color: 'var(--text-muted-green)' }}>
                            {formatDuration(clip)}<br /><span className="text-[11px] text-[#64748B]">{formatTimeRange(clip)}</span>
                          </td>
                          <td>
                            <div className="flex items-center gap-2">
                              <label className="flex items-center gap-1 text-[11px]">
                                <input type="checkbox" checked={!!clip.has_ass} disabled={!!isBusy} onChange={(e) => handleToggle(clip, e.target.checked, !!clip.has_hook)} className="accent-[#B4F105] disabled:opacity-50" /> ASS
                              </label>
                              <label className="flex items-center gap-1 text-[11px]">
                                <input type="checkbox" checked={!!clip.has_hook} disabled={!!isBusy} onChange={(e) => handleToggle(clip, !!clip.has_ass, e.target.checked)} className="accent-[#B4F105] disabled:opacity-50" /> Hook
                              </label>
                              {isRerendering && <span className="h-3 w-3 animate-spin rounded-full border border-white/30 border-t-[#B4F105]" />}
                            </div>
                          </td>
                          <td>
                            {isPublishing ? <span className="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse">Publicando...</span> : isPublished ? <span className="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span> : pb ? <span className={`inline-flex px-2 py-1 rounded-full text-[11px] font-bold border ${pb.cls}`}>{pb.label}</span> : <span className="text-xs text-[#94A3B8]">ready</span>}
                            {(clip.social_post_url || (isPublished && sseUrl)) && <a href={(clip.social_post_url || sseUrl) || '#'} target="_blank" rel="noopener noreferrer" className="ml-2 text-xs text-[#B4F105] hover:underline">Ver</a>}
                          </td>
                          <td>
                            <div className="flex items-center gap-1">
                              <button type="button" onClick={() => setPreviewClip(clip)} className="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Vista previa 9:16"><i className="bi bi-eye" /></button>
                              <button type="button" onClick={() => handleDownload(clip)} className="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Descargar MP4"><i className="bi bi-download" /></button>
                              <button type="button" onClick={() => openPublish(clip)} disabled={!!isBusy} className="btn-custom btn-custom-primary btn-custom-sm !text-xs disabled:opacity-50">
                                {isPublishing ? 'Publicando...' : isPublished ? 'Publicado ✅' : 'Publicar'}
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="table-footer-control" style={{ borderRadius: 'var(--radius-xl)', marginTop: '1rem' }}>
            <span className="table-pagination-info">
              Mostrando <strong style={{ color: 'var(--text-main)' }}>{data.items.length}</strong> de{' '}
              <strong style={{ color: 'var(--text-main)' }}>{data.total}</strong> clips · Página {data.page} de {data.total_pages || 1}
            </span>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="btn-custom btn-custom-light btn-custom-sm">
                Anterior
              </button>
              <span className="table-pagination-info px-2">Página {page} de {totalPages || 1}</span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages || 1, p + 1))}
                className="btn-custom btn-custom-primary btn-custom-sm"
              >
                Siguiente
              </button>
            </div>
          </div>
        </>
      )}

      {/* Modal Preview 9:16 */}
      {previewClip && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={() => setPreviewClip(null)}>
          <div className="relative w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-4 shadow-2xl flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-extrabold text-[#F1F5F9] line-clamp-2">{previewClip.title || 'Clip sin título'}</h3>
                <p className="text-xs font-mono text-[#94A3B8] mt-1">Viral Score: {formatScore(previewClip.score)}/100 · {formatDuration(previewClip)} · {formatTimeRange(previewClip)}</p>
              </div>
              <button onClick={() => setPreviewClip(null)} className="h-8 w-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"><i className="bi bi-x-lg" /></button>
            </div>
            <div className="flex justify-center bg-black rounded-xl overflow-hidden p-2">
              <video
                key={previewClip.id}
                controls
                autoPlay
                playsInline
                src={getVideoSrc(previewClip)}
                className="max-h-[80vh] w-auto mx-auto rounded-lg shadow-2xl"
                style={{ aspectRatio: '9/16', maxWidth: '360px', width: '100%', objectFit: 'contain', background: 'black' }}
              />
            </div>
            {previewClip.transcript && <p className="text-xs leading-relaxed px-2 py-2 rounded-lg bg-[#0B0F17] border border-white/10 text-[#94A3B8] line-clamp-3">{previewClip.transcript}</p>}
            <div className="grid grid-cols-2 gap-2">
              <button type="button" onClick={() => handleDownload(previewClip)} className="btn-custom btn-custom-light !py-2.5 text-xs font-bold flex items-center justify-center gap-1"><i className="bi bi-download" /> Descargar MP4</button>
              <button type="button" onClick={() => { setPreviewClip(null); openPublish(previewClip) }} className="btn-custom btn-custom-primary !py-2.5 text-xs font-bold flex items-center justify-center gap-1"><i className="bi bi-send" /> Publicar</button>
            </div>
            {(previewClip.social_post_url || (sseUrl && activePublishId === previewClip.id)) && (
              <a href={previewClip.social_post_url || sseUrl || '#'} target="_blank" rel="noopener noreferrer" className="text-center text-xs font-bold text-[#B4F105] hover:underline">Ver publicación → {previewClip.social_post_url || sseUrl}</a>
            )}
          </div>
        </div>
      )}

      {publishClip && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setPublishClip(null)}>
          <div className="w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-extrabold text-[#F1F5F9] mb-1">Publicar clip</h3>
            <p className="text-xs text-[#94A3B8] mb-4 line-clamp-2">{publishClip.title || 'Clip sin título'}</p>
            <label className="block text-xs font-bold text-[#CBD5E1] mb-1">Plataforma</label>
            <div className="grid grid-cols-2 gap-2 mb-3">
              {(['tiktok','instagram','youtube','webhook'] as PublishPlatform[]).map((p) => (
                <button key={p} type="button" onClick={() => setPlatform(p)} className={`px-3 py-2.5 rounded-xl text-xs font-bold border capitalize transition ${platform===p ? 'bg-[#B4F105] text-[#080C14] border-[#B4F105] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'bg-[#0B0F17] text-[#94A3B8] border-white/10 hover:border-white/20'}`}>
                  {p === 'youtube' ? 'YouTube Shorts' : p === 'instagram' ? 'Instagram Reels' : p}
                </button>
              ))}
            </div>
            <label className="block text-xs font-bold text-[#CBD5E1] mb-1">Caption</label>
            <textarea value={caption} onChange={(e)=>setCaption(e.target.value)} rows={3} maxLength={500} placeholder="¡Increíble momento de River! #RiverPlate" className="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105] resize-none" />
            <p className="text-[11px] text-[#64748B] text-right mt-1">{caption.length}/500</p>
            {platform==='webhook' && (
              <><label className="block text-xs font-bold text-[#CBD5E1] mt-3 mb-1">Webhook URL (opcional, override)</label><input value={webhookUrl} onChange={(e)=>setWebhookUrl(e.target.value)} placeholder="https://hooks.example.com/publish" className="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105]" /></>
            )}
            <div className="flex gap-2 mt-5">
              <button type="button" onClick={()=>setPublishClip(null)} className="flex-1 btn-custom btn-custom-light">Cancelar</button>
              <button type="button" onClick={submitPublish} disabled={publishing!==null || (ssePublishing && activePublishId===publishClip.id)} className="flex-1 btn-custom btn-custom-primary font-bold disabled:opacity-50 flex items-center justify-center gap-1">
                {publishing || (ssePublishing && activePublishId===publishClip.id) ? <><span className="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" /> Publicando...</> : 'Publicar ahora'}
              </button>
            </div>
            {ssePublishing && activePublishId===publishClip.id && <p className="text-[11px] text-amber-400 mt-2 flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> Escuchando SSE...</p>}
          </div>
        </div>
      )}
    </div>
  )
}
