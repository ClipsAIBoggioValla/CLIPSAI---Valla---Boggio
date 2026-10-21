import { formatScore, formatDuration, formatTimeRange, scoreBadgeClass, publishBadge } from './helpers'
import ClipCard from './ClipCard'
import type { ClipListItem, ClipListResponse } from '@/types/api'

interface ClipResultsProps {
  data: ClipListResponse | null
  loading: boolean
  error: string | null
  viewMode: 'grid' | 'list'
  hasFilters: boolean
  page: number
  totalPages: number
  rerendering: string | null
  publishing: string | null
  ssePublishing: boolean
  sseStatus: string | null
  activePublishId: string | null
  sseUrl: string | null
  onFetchClips: () => void
  onResetFilters: () => void
  onSetPage: (p: number) => void
  setPreviewClip: (c: ClipListItem) => void
  handleDownload: (c: ClipListItem) => void
  handleToggle: (c: ClipListItem, ass: boolean, hook: boolean) => void
  openPublish: (c: ClipListItem) => void
}

export default function ClipResults(props: ClipResultsProps) {
  const {
    data, loading, error, viewMode, hasFilters, page, totalPages,
    rerendering, publishing, ssePublishing, sseStatus, activePublishId, sseUrl,
    onFetchClips, onResetFilters, onSetPage, setPreviewClip, handleDownload, handleToggle, openPublish,
  } = props

  if (loading) {
    return (
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
    )
  }

  if (error && !loading) {
    return (
      <div role="alert" className="alert-custom alert-custom-danger">
        <i className="bi bi-exclamation-circle-fill alert-custom-icon" />
        <div className="alert-custom-content">{error}</div>
        <button onClick={onFetchClips} className="btn-custom btn-custom-danger btn-custom-sm">Reintentar</button>
      </div>
    )
  }

  if (!loading && !error && data && data.items.length === 0) {
    return (
      <div className="card-spark text-center" style={{ borderStyle: 'dashed', padding: '2.5rem', borderColor: 'rgba(180,241,5,0.18)' }}>
        <div className="h-12 w-12 rounded-full flex items-center justify-center text-xl mx-auto bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.06)]">🎬</div>
        <p className="text-sm font-bold mt-4" style={{ color: '#F1F5F9' }}>No hay clips que coincidan</p>
        <p className="text-xs mt-1" style={{ color: '#94A3B8' }}>Prueba ajustando la búsqueda, el filtro de score o el ordenamiento.</p>
        {hasFilters && (<button onClick={onResetFilters} className="btn-custom btn-custom-primary mt-5">Limpiar filtros</button>)}
      </div>
    )
  }

  if (!loading && !error && data && data.items.length > 0) {
    return (
      <>
        {viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((clip) => {
              const isRerendering = rerendering === clip.id
              const isPublishing = publishing === clip.id || (ssePublishing && activePublishId === clip.id)
              const isBusy = isRerendering || isPublishing || clip.status === 'PUBLISHING'
              const isPublished = clip.status === 'PUBLISHED' || (sseStatus === 'PUBLISHED' && activePublishId === clip.id)
              return (
                <ClipCard key={clip.id} clip={clip} isRerendering={isRerendering} isPublishing={isPublishing} isBusy={isBusy} isPublished={isPublished} sseUrl={sseUrl} onPreview={setPreviewClip} onDownload={handleDownload} onToggle={handleToggle} onOpenPublish={openPublish} />
              )
            })}
          </div>
        ) : (
          <div className="table-card-custom">
            <div className="table-responsive" style={{ overflowX: 'auto' }}>
              <table className="table-custom">
                <thead>
                  <tr><th>Título</th><th>Viral Score</th><th>Duración</th><th>ASS / Hook</th><th>Estado</th><th>Acción</th></tr>
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
                          <p className="font-bold line-clamp-1 cursor-pointer hover:text-[#B4F105]" style={{ color: 'var(--text-main)' }} onClick={() => setPreviewClip(clip)}>{clip.title || 'Sin título'}</p>
                          {clip.transcript && <p className="text-xs line-clamp-1 mt-1" style={{ color: 'var(--text-muted-green)' }}>{clip.transcript}</p>}
                        </td>
                        <td><span className={scoreBadgeClass(clip.score)}>Viral Score: {formatScore(clip.score)}/100</span></td>
                        <td className="font-mono text-xs" style={{ color: 'var(--text-muted-green)' }}>{formatDuration(clip)}<br /><span className="text-[11px] text-[#64748B]">{formatTimeRange(clip)}</span></td>
                        <td>
                          <div className="flex items-center gap-2">
                            <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={!!clip.has_ass} disabled={!!isBusy} onChange={(e) => handleToggle(clip, e.target.checked, !!clip.has_hook)} className="accent-[#B4F105] disabled:opacity-50" /> ASS</label>
                            <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={!!clip.has_hook} disabled={!!isBusy} onChange={(e) => handleToggle(clip, !!clip.has_ass, e.target.checked)} className="accent-[#B4F105] disabled:opacity-50" /> Hook</label>
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
                            <button type="button" onClick={() => openPublish(clip)} disabled={!!isBusy} className="btn-custom btn-custom-primary btn-custom-sm !text-xs disabled:opacity-50">{isPublishing ? 'Publicando...' : isPublished ? 'Publicado ✅' : 'Publicar'}</button>
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
          <span className="table-pagination-info">Mostrando <strong style={{ color: 'var(--text-main)' }}>{data.items.length}</strong> de <strong style={{ color: 'var(--text-main)' }}>{data.total}</strong> clips · Página {data.page} de {data.total_pages || 1}</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => onSetPage(Math.max(1, page - 1))} className="btn-custom btn-custom-light btn-custom-sm">Anterior</button>
            <span className="table-pagination-info px-2">Página {page} de {totalPages || 1}</span>
            <button disabled={page >= totalPages} onClick={() => onSetPage(Math.min(totalPages || 1, page + 1))} className="btn-custom btn-custom-primary btn-custom-sm">Siguiente</button>
          </div>
        </div>
      </>
    )
  }

  return null
}
