import type { MetricsResponse, StatsSummary } from '@/types/api'

interface KpiGridProps {
  stats: StatsSummary | null
  metrics: MetricsResponse
}

export default function KpiGrid(props: KpiGridProps) {
  const { stats, metrics } = props
  function formatHours(hours: number): string {
    if (hours === 0) return '0h'
    if (hours < 1) return `${Math.round(hours * 60)} min`
    if (hours % 1 === 0) return `${hours}h`
    return `${hours.toFixed(1)}h`
  }
  function scoreBadge(score: number) {
    if (score >= 71) return 'high'
    if (score >= 41) return 'mid'
    return 'low'
  }
  function scoreLabel(score: number): string {
    if (score >= 71) return 'Alto'
    if (score >= 41) return 'Medio'
    return 'Bajo'
  }
  return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="kpi-card">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Procesamientos</p>
            <span className="kpi-accent"><i className="bi bi-film" /></span>
          </div>
          <p className="text-3xl font-extrabold mt-3 text-[var(--text-primary)] tracking-tight">{metrics.total_jobs}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{stats ? `${stats.total_videos} videos subidos` : 'Videos enviados'}</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Total Clips</p>
            <span className="kpi-accent"><i className="bi bi-collection-play" /></span>
          </div>
          <p className="text-3xl font-extrabold mt-3 text-[var(--text-primary)] tracking-tight">{metrics.total_clips}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">Clips virales extraídos</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Tiempo Ahorrado</p>
            <span className="kpi-accent"><i className="bi bi-lightning-charge" /></span>
          </div>
          <p className="text-3xl font-extrabold mt-3 text-[var(--brand-lime)] tracking-tight">{formatHours(metrics.time_saved_hours)}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">Estimado · {metrics.total_minutes_processed} min procesados</p>
        </div>
        <div className="kpi-card">
          {stats ? (
            <>
              <p className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Potencial viral promedio</p>
              <div className="flex items-center gap-3 mt-3">
                <p className="text-3xl font-extrabold text-[var(--text-primary)] tracking-tight">{stats.avg_score.toFixed(1)}</p>
                <span className={`score-badge-neon ${scoreBadge(stats.avg_score)}`}>
                  {scoreLabel(stats.avg_score)}
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1">Promedio de tus clips</p>
            </>
          ) : (
            <>
              <p className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Minutos Procesados</p>
              <p className="text-3xl font-extrabold mt-3 text-[var(--text-primary)]">{metrics.total_minutes_processed}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">Acumulado total</p>
            </>
          )}
        </div>
      </div>
  )
}
