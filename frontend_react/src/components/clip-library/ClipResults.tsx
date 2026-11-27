import { formatScore, formatDuration, formatTimeRange, scoreBadgeClass, publishBadge, publishStatusLabel } from './helpers'
import ClipCard from './ClipCard'
import type { ClipListItem, ClipListResponse } from '@/types/api'

type ClipFlags = {
  isRerendering: boolean
  isPublishing: boolean
  isBusy: boolean
  isPublished: boolean
}

function isPublishingFlag(
  clipId: string,
  publishing: string | null,
  ssePublishing: boolean,
  activePublishId: string | null,
): boolean {
  if (publishing === clipId) return true
  return ssePublishing && activePublishId === clipId
}

function isPublishedFlag(
  clip: ClipListItem,
  sseStatus: string | null,
  activePublishId: string | null,
): boolean {
  if (clip.status === 'PUBLISHED') return true
  return sseStatus === 'PUBLISHED' && activePublishId === clip.id
}

function clipFlags(
  clip: ClipListItem,
  rerendering: string | null,
  publishing: string | null,
  ssePublishing: boolean,
  sseStatus: string | null,
  activePublishId: string | null,
): ClipFlags {
  const isRerendering = rerendering === clip.id
  const isPublishing = isPublishingFlag(clip.id, publishing, ssePublishing, activePublishId)
  const isPublished = isPublishedFlag(clip, sseStatus, activePublishId)
  return {
    isRerendering,
    isPublishing,
    isPublished,
    isBusy: isRerendering || isPublishing,
  }
}

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
  onEdit: (c: ClipListItem) => void
}

export default function ClipResults(props: ClipResultsProps) {
  const {
    data, loading, error, viewMode, hasFilters, page, totalPages,
    rerendering, publishing, ssePublishing, sseStatus, activePublishId, sseUrl,
    onFetchClips, onResetFilters, onSetPage, setPreviewClip, handleDownload, handleToggle, openPublish, onEdit,
  } = props

  if (loading) {
    return (
      <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="card-spark animate-pulse">
            <div className="h-4 bg-white/5 rounded w-3/4 mb-3" />
            <div className="h-3 bg-white/5 rounded w-1/2 mb-4" />
            <div className="h-10 bg-white/5 rounded mb-3" />
            <div className="h-3 bg-white/5 rounded w-1/3" />
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
      <div className="card-spark text-center" style={{ borderStyle: 'dashed', padding: '2.5rem', borderColor: 'var(--border-subtle)' }}>
        <div className="h-12 w-12 rounded-full flex items-center justify-center text-xl mx-auto bg-white/5 border border-[var(--border-subtle)]">🎬</div>
        <p className="text-sm font-bold mt-4 text-[var(--text-primary)]">No hay clips que coincidan</p>
        <p className="text-xs mt-1 text-[var(--text-secondary)]">Prueba ajustando la búsqueda, el potencial viral o el orden.</p>
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
              const flags = clipFlags(clip, rerendering, publishing, ssePublishing, sseStatus, activePublishId)
              const isBusy = flags.isBusy || clip.status === 'PUBLISHING'
              return (
                <ClipCard key={clip.id} clip={clip} isRerendering={flags.isRerendering} isPublishing={flags.isPublishing} isBusy={isBusy} isPublished={flags.isPublished} sseUrl={sseUrl} onPreview={setPreviewClip} onDownload={handleDownload} onToggle={handleToggle} onOpenPublish={openPublish} onEdit={onEdit} />
              )
            })}
          </div>
        ) : (
          <div className="table-card-custom">
            <div className="table-responsive" style={{ overflowX: 'auto' }}>
              <table className="table-custom">
                <thead>
                  <tr><th>Título</th><th>Potencial viral</th><th>Duración</th><th>Subtítulos / Gancho</th><th>Estado</th><th>Acción</th></tr>
                </thead>
                <tbody>
                  {data.items.map((clip) => {
                    const pb = publishBadge(clip.status)
                    const flags = clipFlags(clip, rerendering, publishing, ssePublishing, sseStatus, activePublishId)
                    const isRerendering = flags.isRerendering
                    const isPublishing = flags.isPublishing
                    const isBusy = flags.isBusy
                    const isPublished = flags.isPublished
                    return (
                      <tr key={clip.id} className={isRerendering ? 'opacity-60' : ''}>
                        <td>
                          <p className="font-bold line-clamp-1 cursor-pointer text-[var(--text-primary)] hover:text-[var(--brand-lime)]" onClick={() => setPreviewClip(clip)}>{clip.title || 'Sin título'}</p>
                          {clip.transcript && <p className="text-xs line-clamp-1 mt-1 text-[var(--text-secondary)]">{clip.transcript}</p>}
                        </td>
                        <td><span className={scoreBadgeClass(clip.score)}>Potencial viral: {formatScore(clip.score)}/100</span></td>
                        <td className="font-mono text-xs text-[var(--text-secondary)]">{formatDuration(clip)}<br /><span className="text-[11px]">{formatTimeRange(clip)}</span></td>
                        <td>
                          <div className="flex items-center gap-2">
                            <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={!!clip.has_ass} disabled={!!isBusy} onChange={(e) => handleToggle(clip, e.target.checked, !!clip.has_hook)} className="accent-[var(--brand-lime)] disabled:opacity-50" /> Subtítulos</label>
                            <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={!!clip.has_hook} disabled={!!isBusy} onChange={(e) => handleToggle(clip, !!clip.has_ass, e.target.checked)} className="accent-[var(--brand-lime)] disabled:opacity-50" /> Gancho</label>
                            {isRerendering && <span className="h-3 w-3 animate-spin rounded-full border border-white/30 border-t-[var(--brand-lime)]" />}
                          </div>
                        </td>
                        <td>
                          {isPublishing ? <span className="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse">Publicando...</span> : isPublished ? <span className="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span> : pb ? <span className={`inline-flex px-2 py-1 rounded-full text-[11px] font-bold border ${pb.cls}`}>{publishStatusLabel(pb.label)}</span> : <span className="text-xs text-[var(--text-secondary)]">Listo</span>}
                          {(clip.social_post_url || (isPublished && sseUrl)) && <a href={(clip.social_post_url || sseUrl) || '#'} target="_blank" rel="noopener noreferrer" className="ml-2 text-xs text-[var(--brand-lime)] hover:underline">Ver</a>}
                        </td>
                        <td>
                          <div className="flex items-center gap-1">
                            <button type="button" onClick={() => setPreviewClip(clip)} className="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Vista previa vertical"><i className="bi bi-eye" /></button>
                            <button type="button" onClick={() => handleDownload(clip)} className="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Descargar MP4"><i className="bi bi-download" /></button>
                            <button type="button" onClick={() => onEdit(clip)} disabled={!!isBusy} className="btn-custom btn-custom-light btn-custom-sm !text-xs disabled:opacity-50" title="Editar clip"><i className="bi bi-pencil-square" /></button>
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
