import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { clipService } from '@/services/api'
import type { ClipListItem, ClipListResponse, ClipSortBy } from '@/types/api'
import { ApiError } from '@/types/api'

type ViewMode = 'grid' | 'list'

function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—'
  return score.toFixed(1)
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

export default function ClipLibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlQ = searchParams.get('q') ?? ''
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

  useEffect(() => {
    if (urlQ !== q) setQ(urlQ)
  }, [urlQ])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 350)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    setPage(1)
  }, [debouncedQ, minScore, sortBy])

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
      })
      setData(res)
    } catch (err: unknown) {
      if (err instanceof ApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError('Error al cargar clips')
    } finally {
      setLoading(false)
    }
  }, [debouncedQ, minScore, sortBy, page, limit])

  useEffect(() => {
    fetchClips()
  }, [fetchClips])

  const hasFilters = debouncedQ !== '' || minScore !== '' || sortBy !== 'created_at_desc'
  const totalPages = data?.total_pages ?? 0

  function resetFilters() {
    setQ('')
    setDebouncedQ('')
    setMinScore('')
    setSortBy('created_at_desc')
    setPage(1)
    const next = new URLSearchParams(searchParams)
    next.delete('q')
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="max-w-6xl mx-auto">
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
              {data.items.map((clip) => (
                <div key={clip.id} className="clip-card" style={{ marginBottom: 0 }}>
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-bold line-clamp-2 flex-1" style={{ color: '#F1F5F9' }}>
                      {clip.title || 'Clip sin título'}
                    </h3>
                    <span className={scoreBadgeClass(clip.score)}>{formatScore(clip.score)}</span>
                  </div>
                  <p className="text-xs font-mono px-2.5 py-1.5 rounded-full border inline-flex items-center gap-1.5" style={{ color: '#94A3B8', background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}>
                    <i className="bi bi-clock" style={{ fontSize: '0.7rem' }} /> {formatTimeRange(clip)} · {new Date(clip.created_at).toLocaleDateString()}
                  </p>
                  {clip.transcript ? (
                    <p className="text-sm line-clamp-3 leading-relaxed rounded-xl px-3 py-2.5 border" style={{ color: '#CBD5E1', background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.06)' }}>
                      {clip.transcript}
                    </p>
                  ) : (
                    <p className="text-xs italic" style={{ color: '#64748B' }}>
                      Sin transcripción disponible
                    </p>
                  )}
                  <div className="flex items-center gap-1.5 pt-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.5)]" />
                    <span className="text-[11px] font-semibold tracking-wide uppercase" style={{ color: '#94A3B8' }}>Listo para publicar</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="table-card-custom">
              <div className="table-responsive" style={{ overflowX: 'auto' }}>
                <table className="table-custom">
                  <thead>
                    <tr>
                      <th>Título</th>
                      <th>Score</th>
                      <th>Inicio - Fin</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((clip) => (
                      <tr key={clip.id}>
                        <td>
                          <p className="font-bold line-clamp-1" style={{ color: 'var(--text-main)' }}>
                            {clip.title || 'Sin título'}
                          </p>
                          {clip.transcript && <p className="text-xs line-clamp-1 mt-1" style={{ color: 'var(--text-muted-green)' }}>{clip.transcript}</p>}
                        </td>
                        <td>
                          <span className={scoreBadgeClass(clip.score)}>{formatScore(clip.score)}</span>
                        </td>
                        <td className="font-mono text-xs" style={{ color: 'var(--text-muted-green)' }}>
                          {formatTimeRange(clip)}
                        </td>
                        <td className="text-xs" style={{ color: 'var(--text-muted-green)' }}>
                          {new Date(clip.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
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
    </div>
  )
}
