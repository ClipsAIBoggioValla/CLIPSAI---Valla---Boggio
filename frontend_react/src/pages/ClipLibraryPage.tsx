import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { clipService } from '@/services/api'
import type { ClipListItem, ClipListResponse, ClipSortBy, PublishPlatform } from '@/types/api'
import { ApiError } from '@/types/api'
import { usePublishSSE } from '@/hooks/usePublishSSE'
import FilterBar from '@/components/clip-library/FilterBar'
import ClipResults from '@/components/clip-library/ClipResults'
import PublishDialog from '@/components/clip-library/PublishDialog'
import PreviewModal from '@/components/clip-library/PreviewModal'
import ClipLibraryHeader from '@/components/clip-library/ClipLibraryHeader'
import { getVideoSrc } from '@/components/clip-library/helpers'

type ViewMode = 'grid' | 'list'

const RAW_BASE: string =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()
const API_BASE_URL = (RAW_BASE || 'https://clipsai-backend.onrender.com').replace(/\/$/, '')

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

  useEffect(() => { if (urlQ !== q) setQ(urlQ) }, [urlQ])
  useEffect(() => { const t = setTimeout(() => setDebouncedQ(q), 350); return () => clearTimeout(t) }, [q])
  useEffect(() => { setPage(1) }, [debouncedQ, minScore, sortBy, jobId])

  const fetchClips = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await clipService.getClips({ q: debouncedQ || undefined, min_score: minScore ? Number(minScore) : undefined, sort_by: sortBy, page, limit, job_id: jobId })
      const sortedItems = [...res.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      setData({ ...res, items: sortedItems })
    } catch (err: unknown) {
      if (err instanceof ApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError('Error al cargar clips')
    } finally { setLoading(false) }
  }, [debouncedQ, minScore, sortBy, page, limit, jobId])

  useEffect(() => { fetchClips() }, [fetchClips])

  useEffect(() => {
    if (!activePublishId || !sseStatus) return
    const term = sseStatus.toUpperCase()
    if (term === 'PUBLISHED') {
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === activePublishId ? { ...c, status: 'PUBLISHED', social_post_url: sseUrl || c.social_post_url, published_platform: c.published_platform } : c) } : prev)
      setToast(`Publicado \u2705 ${sseUrl ? sseUrl : ''}`.trim())
      setPublishing(null); setActivePublishId(null)
      setTimeout(() => setToast(null), 4000); fetchClips()
    } else if (term === 'FAILED') {
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === activePublishId ? { ...c, status: 'FAILED' } : c) } : prev)
      setToast('Error al publicar — FAILED'); setPublishing(null); setActivePublishId(null)
      setTimeout(() => setToast(null), 4000)
    } else if (term === 'PUBLISHING') {
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === activePublishId ? { ...c, status: 'PUBLISHING' } : c) } : prev)
    }
  }, [sseStatus, sseUrl, activePublishId, fetchClips])

  useEffect(() => { if (ssePublishing && activePublishId) setPublishing(activePublishId) }, [ssePublishing, activePublishId])

  const hasFilters = debouncedQ !== '' || minScore !== '' || sortBy !== 'created_at_desc' || !!jobId
  const totalPages = data?.total_pages ?? 0

  function resetFilters() {
    setQ(''); setDebouncedQ(''); setMinScore(''); setSortBy('created_at_desc'); setPage(1)
    const next = new URLSearchParams(searchParams); next.delete('q'); next.delete('job_id')
    setSearchParams(next, { replace: true })
  }

  function openPublish(clip: ClipListItem) {
    setPublishClip(clip); setPlatform('tiktok')
    setCaption(clip.title ? `${clip.title} #viral` : '¡Increíble momento! #RiverPlate')
    setWebhookUrl('')
  }

  async function submitPublish() {
    if (!publishClip) return
    const clipId = publishClip.id; const plat = platform; const cap = caption; const wh = webhookUrl
    setPublishing(clipId)
    try {
      await clipService.publishClip(clipId, { platform: plat, caption: cap || undefined, webhook_override_url: plat === 'webhook' && wh ? wh : undefined })
      setActivePublishId(clipId)
      setToast(`Publicación en ${plat} encolada — PUBLISHING`)
      setPublishClip(null)
      setData((prev) => prev ? { ...prev, items: prev.items.map((c) => c.id === clipId ? { ...c, status: 'PUBLISHING', published_platform: plat } : c) } : prev)
      setTimeout(() => setToast(null), 4000)
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error al publicar'
      setToast(msg); setPublishing(null); setActivePublishId(null)
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
      setToast(msg); setTimeout(() => setToast(null), 4000)
    } finally { setRerendering(null) }
  }

  const handleDownload = async (clip: ClipListItem) => { await clipService.downloadClip(clip) }

  return (
    <div className="max-w-6xl mx-auto">
      {toast && <div className="fixed top-4 right-4 z-[9999] bg-[#121824] border border-[#B4F105]/30 text-[#F1F5F9] px-4 py-3 rounded-xl shadow-xl text-sm font-semibold">{toast}</div>}
      <ClipLibraryHeader total={data?.total ?? 0} jobId={jobId} />

      <FilterBar q={q} setQ={setQ} minScore={minScore} setMinScore={setMinScore} sortBy={sortBy} setSortBy={setSortBy} viewMode={viewMode} setViewMode={setViewMode} hasFilters={hasFilters} resetFilters={resetFilters} />

      <ClipResults
        data={data} loading={loading} error={error} viewMode={viewMode} hasFilters={hasFilters} page={page} totalPages={totalPages}
        rerendering={rerendering} publishing={publishing} ssePublishing={ssePublishing} sseStatus={sseStatus} activePublishId={activePublishId} sseUrl={sseUrl}
        onFetchClips={fetchClips} onResetFilters={resetFilters} onSetPage={setPage} setPreviewClip={setPreviewClip} handleDownload={handleDownload} handleToggle={handleToggle} openPublish={openPublish}
      />

      {previewClip && <PreviewModal clip={previewClip} sseUrl={sseUrl} activePublishId={activePublishId} onClose={() => setPreviewClip(null)} onDownload={handleDownload} onOpenPublish={(c) => { setPreviewClip(null); openPublish(c) }} getVideoSrc={(c) => getVideoSrc(c, API_BASE_URL)} />}
      {publishClip && <PublishDialog clip={publishClip} platform={platform} setPlatform={setPlatform} caption={caption} setCaption={setCaption} webhookUrl={webhookUrl} setWebhookUrl={setWebhookUrl} publishing={publishing} onClose={() => setPublishClip(null)} onSubmit={submitPublish} ssePublishing={ssePublishing} activePublishId={activePublishId} />}
    </div>
  )
}
