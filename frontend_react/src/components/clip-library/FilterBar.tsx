import type { ClipSortBy } from '@/types/api'

interface FilterBarProps {
  q: string
  setQ: (v: string) => void
  minScore: string
  setMinScore: (v: string) => void
  sortBy: ClipSortBy
  setSortBy: (v: ClipSortBy) => void
  viewMode: 'grid' | 'list'
  setViewMode: (v: 'grid' | 'list') => void
  hasFilters: boolean
  resetFilters: () => void
}

export default function FilterBar(props: FilterBarProps) {
  const { q, setQ, minScore, setMinScore, sortBy, setSortBy, viewMode, setViewMode, hasFilters, resetFilters } = props
  return (
    <>
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] mb-4 min-h-14">
        <div className="relative flex-1 max-w-md w-full">
          <i className="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por título o transcripción..."
            className="form-control-custom pl-9 py-2"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <select value={minScore} onChange={(e) => setMinScore(e.target.value)} className="form-select-custom w-auto text-xs px-3 py-2 cursor-pointer">
            <option value="">Todos los potenciales</option>
            <option value="70">+70 Alto</option>
            <option value="40">+40 Medio</option>
          </select>

          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as ClipSortBy)} className="form-select-custom w-auto text-xs px-3 py-2 cursor-pointer">
            <option value="created_at_desc">Más recientes</option>
            <option value="created_at_asc">Más antiguos</option>
            <option value="score_desc">Mayor potencial</option>
            <option value="score_asc">Menor potencial</option>
          </select>

          <div className="py-1 px-1 bg-[var(--bg-app)] border border-[var(--border-subtle)] rounded-lg flex items-center gap-1">
            <button type="button" onClick={() => setViewMode('grid')} className={`px-3 py-1.5 rounded-md text-xs font-bold transition ${viewMode === 'grid' ? 'bg-lime-accent text-[var(--bg-sidebar)] shadow-[var(--brand-lime-glow)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`} aria-label="Vista de tarjetas">
              ⊞ Grid
            </button>
            <button type="button" onClick={() => setViewMode('list')} className={`px-3 py-1.5 rounded-md text-xs font-bold transition ${viewMode === 'list' ? 'bg-lime-accent text-[var(--bg-sidebar)] shadow-[var(--brand-lime-glow)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`} aria-label="Vista de tabla">
              ☰ Lista
            </button>
          </div>
        </div>
      </div>

      {hasFilters && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-bold text-[var(--text-secondary)]">Filtros activos</span>
          <button onClick={resetFilters} className="btn-custom btn-custom-light btn-custom-sm !py-1 !text-xs">
            Resetear filtros
          </button>
        </div>
      )}
    </>
  )
}
