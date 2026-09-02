import { useEffect, useState, useCallback } from 'react'
import { clipService } from '@/services/api'
import type { ClipListItem, ClipListResponse, ClipSortBy } from '@/types/api'
import { ApiError } from '@/types/api'

type ViewMode = 'grid' | 'list'

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

function formatTimeRange(item: ClipListItem): string {
  return `${item.start_time.toFixed(1)}s — ${item.end_time.toFixed(1)}s`
}

export default function ClipLibraryPage() {
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [minScore, setMinScore] = useState<string>('')
  const [sortBy, setSortBy] = useState<ClipSortBy>('created_at_desc')
  const [page, setPage] = useState(1)
  const [limit] = useState(10)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [data, setData] = useState<ClipListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Biblioteca de Clips</h1>
          <p className="text-sm text-gray-400 mt-2">Explora, busca y gestiona todos tus clips generados con filtros y paginación.</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 sm:p-5 mb-6">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col lg:flex-row gap-3">
              <div className="relative flex-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
                <input
                  type="text"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Buscar por título o transcripción..."
                  className="w-full rounded-xl bg-gray-800 border border-gray-700 pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition"
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <select
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                  className="rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  <option value="">Todos los scores</option>
                  <option value="70">+70 Alto</option>
                  <option value="40">+40 Medio</option>
                </select>

                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as ClipSortBy)}
                  className="rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  <option value="created_at_desc">Más recientes</option>
                  <option value="created_at_asc">Más antiguos</option>
                  <option value="score_desc">Mayor score</option>
                  <option value="score_asc">Menor score</option>
                </select>

                <div className="flex rounded-xl bg-gray-800 border border-gray-700 p-1">
                  <button
                    type="button"
                    onClick={() => setViewMode('grid')}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${viewMode === 'grid' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white'}`}
                    aria-label="Vista de tarjetas"
                  >
                    ⊞ Grid
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('list')}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${viewMode === 'list' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white'}`}
                    aria-label="Vista de tabla"
                  >
                    ☰ Lista
                  </button>
                </div>
              </div>
            </div>

            {hasFilters && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Filtros activos</span>
                <button
                  onClick={resetFilters}
                  className="text-xs font-medium text-violet-400 hover:text-violet-300 border border-violet-500/30 hover:border-violet-500/50 rounded-full px-3 py-1 transition"
                >
                  Resetear filtros
                </button>
              </div>
            )}
          </div>
        </div>

        {loading && (
          <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-2xl bg-gray-900 border border-gray-800 p-5 animate-pulse">
                <div className="h-4 bg-gray-800 rounded w-3/4 mb-3" />
                <div className="h-3 bg-gray-800 rounded w-1/2 mb-4" />
                <div className="h-10 bg-gray-800 rounded mb-3" />
                <div className="h-3 bg-gray-800 rounded w-1/3" />
              </div>
            ))}
          </div>
        )}

        {error && !loading && (
          <div role="alert" className="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-center">
            <p className="text-sm text-red-300">{error}</p>
            <button onClick={fetchClips} className="mt-4 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-xl px-4 py-2 transition">Reintentar</button>
          </div>
        )}

        {!loading && !error && data && data.items.length === 0 && (
          <div className="rounded-2xl bg-gray-900 border border-dashed border-gray-700 p-10 text-center">
            <div className="h-12 w-12 rounded-full bg-gray-800 flex items-center justify-center text-xl mx-auto">🎬</div>
            <p className="text-sm font-medium text-gray-200 mt-4">No hay clips que coincidan</p>
            <p className="text-xs text-gray-500 mt-1">Prueba ajustando la búsqueda, el filtro de score o el ordenamiento.</p>
            {hasFilters && (
              <button onClick={resetFilters} className="mt-5 inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium py-2.5 px-5 transition">Limpiar filtros</button>
            )}
          </div>
        )}

        {!loading && !error && data && data.items.length > 0 && (
          <>
            {viewMode === 'grid' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.items.map((clip) => (
                  <div key={clip.id} className="rounded-2xl bg-gray-900 border border-gray-800 p-5 flex flex-col gap-3 hover:border-gray-700 transition">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-semibold text-white line-clamp-2 flex-1">{clip.title || 'Clip sin título'}</h3>
                      <span className={`shrink-0 inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreBadge(clip.score)}`}>
                        {formatScore(clip.score)}
                      </span>
                    </div>
                    <p className="text-xs font-mono text-gray-400 bg-gray-800/60 rounded-lg px-2.5 py-1.5 border border-gray-800">{formatTimeRange(clip)} · {new Date(clip.created_at).toLocaleDateString()}</p>
                    {clip.transcript ? (
                      <p className="text-sm text-gray-300 line-clamp-3 leading-relaxed bg-gray-800/40 rounded-lg px-3 py-2">{clip.transcript}</p>
                    ) : (
                      <p className="text-xs text-gray-500 italic">Sin transcripción disponible</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl bg-gray-900 border border-gray-800 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800/50 text-xs text-gray-400 uppercase">
                      <tr>
                        <th className="text-left px-4 py-3 font-medium">Título</th>
                        <th className="text-left px-4 py-3 font-medium">Score</th>
                        <th className="text-left px-4 py-3 font-medium">Inicio - Fin</th>
                        <th className="text-left px-4 py-3 font-medium">Fecha</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {data.items.map((clip) => (
                        <tr key={clip.id} className="hover:bg-gray-800/30 transition">
                          <td className="px-4 py-3">
                            <p className="font-medium text-white line-clamp-1">{clip.title || 'Sin título'}</p>
                            {clip.transcript && <p className="text-xs text-gray-400 line-clamp-1 mt-1">{clip.transcript}</p>}
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${scoreBadge(clip.score)}`}>{formatScore(clip.score)}</span>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-gray-400">{formatTimeRange(clip)}</td>
                          <td className="px-4 py-3 text-xs text-gray-400">{new Date(clip.created_at).toLocaleDateString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-6 bg-gray-900 border border-gray-800 rounded-2xl px-4 py-3">
              <p className="text-xs text-gray-400">
                Mostrando <span className="text-white font-medium">{data.items.length}</span> de <span className="text-white font-medium">{data.total}</span> clips · Página {data.page} de {data.total_pages || 1}
              </p>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-4 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm font-medium text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-700 transition"
                >
                  Anterior
                </button>
                <span className="text-xs text-gray-400 px-2">Página {page} de {totalPages || 1}</span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages || 1, p + 1))}
                  className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium transition"
                >
                  Siguiente
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
