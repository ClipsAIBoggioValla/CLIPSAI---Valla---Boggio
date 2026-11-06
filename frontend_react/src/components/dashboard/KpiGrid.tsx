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
    if (score >= 71) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    if (score >= 41) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
    return 'bg-red-500/15 text-red-300 border-red-500/30'
  }
  return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="kpi-card">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Total Videos / Jobs</p>
            <span className="kpi-accent"><i className="bi bi-film" /></span>
          </div>
          <p className="text-3xl font-extrabold mt-3 text-white tracking-tight">{metrics.total_jobs}</p>
          <p className="text-xs text-[#94A3B8] mt-1">{stats ? `${stats.total_videos} videos subidos` : 'Jobs procesados'}</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Total Clips</p>
            <span className="kpi-accent"><i className="bi bi-collection-play" /></span>
          </div>
          <p className="text-3xl font-extrabold mt-3 text-white tracking-tight">{metrics.total_clips}</p>
          <p className="text-xs text-[#94A3B8] mt-1">Clips virales extraídos</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Tiempo Ahorrado</p>
            <span className="kpi-accent !bg-[rgba(180,241,5,0.14)] !border-[rgba(180,241,5,0.25)] !text-[#B4F105]"><i className="bi bi-lightning-charge" /></span>
          </div>
          <p className="text-3xl font-extrabold mt-3 text-[#B4F105] tracking-tight" style={{ textShadow: '0 0 16px rgba(180,241,5,0.35)' }}>{formatHours(metrics.time_saved_hours)}</p>
          <p className="text-xs text-[#94A3B8] mt-1">Estimado · {metrics.total_minutes_processed} min procesados</p>
        </div>
        <div className="kpi-card">
          {stats ? (
            <>
              <p className="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Promedio Viralidad</p>
              <div className="flex items-center gap-3 mt-3">
                <p className="text-3xl font-extrabold text-white tracking-tight">{stats.avg_score.toFixed(1)}</p>
                <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${scoreBadge(stats.avg_score)}`}>
                  {stats.avg_score >= 71 ? 'Alto' : stats.avg_score >= 41 ? 'Medio' : 'Bajo'}
                </span>
              </div>
              <p className="text-xs text-[#94A3B8] mt-1">Score promedio de tus clips</p>
            </>
          ) : (
            <>
              <p className="text-xs font-bold text-[#94A3B8] uppercase tracking-widest">Minutos Procesados</p>
              <p className="text-3xl font-extrabold mt-3 text-white">{metrics.total_minutes_processed}</p>
              <p className="text-xs text-[#94A3B8] mt-1">Acumulado total</p>
            </>
          )}
        </div>
      </div>
  )
}
