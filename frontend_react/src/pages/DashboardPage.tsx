import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { metricsService, statsService } from '@/services/api'
import type { MetricsResponse, StatsSummary } from '@/types/api'
import { ApiError } from '@/types/api'

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

function KpiSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 animate-pulse">
          <div className="h-3 bg-[rgba(255,255,255,0.06)] rounded w-1/2 mb-4" />
          <div className="h-8 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-2" />
          <div className="h-3 bg-[rgba(255,255,255,0.04)] rounded w-2/3" />
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  useEffect(() => {
    try {
      const id = localStorage.getItem('clipsai_active_job_id')
      if (id) setActiveJobId(id)
    } catch {}
  }, [])

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, m] = await Promise.all([statsService.getSummary(), metricsService.getMetrics()])
      setStats(s)
      setMetrics(m)
    } catch (err: unknown) {
      if (err instanceof ApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError('Error al cargar métricas')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  // Timeout de seguridad 5s para evitar spinner infinito si la petición inicial se cuelga
  useEffect(() => {
    if (!loading) return
    const t = window.setTimeout(() => setLoading(false), 5000)
    return () => window.clearTimeout(t)
  }, [loading])

  // Barras CSS (paridad con Vue) — sin dependencia de gráficos.
  const maxCount = stats
    ? Math.max(1, ...stats.score_distribution.map((d) => d.count))
    : 1

  const barColors: Record<string, string> = {
    Bajo: '#ef4444',
    Medio: '#f59e0b',
    Alto: '#10b981',
  }

  const platformEntries: { platform: string; count: number }[] = metrics
    ? Object.entries(metrics.platform_distribution).map(([platform, count]) => ({ platform, count }))
    : []

  const platformColors: Record<string, string> = {
    tiktok: '#EC4899',
    youtube: '#EF4444',
    instagram: '#8B5CF6',
  }

  const hasPlatformData = platformEntries.some((d) => d.count > 0)

  const maxPlatform = platformEntries.length
    ? Math.max(1, ...platformEntries.map((e) => e.count))
    : 1

  const maxRecent = metrics
    ? Math.max(1, ...metrics.recent_activity.map((d) => Math.max(d.jobs, d.clips, d.minutes_processed)))
    : 1

  const isEmpty = metrics && metrics.total_jobs === 0 && metrics.total_clips === 0

  const chartCardClass = 'rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 sm:p-6 shadow-xl'

  return (
    <div className="min-h-screen bg-[#0B0F17] text-white">
      <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
        {activeJobId && (
          <div className="rounded-xl border border-[rgba(180,241,5,0.22)] bg-[rgba(180,241,5,0.08)] px-4 py-3 flex items-center justify-between gap-3 mb-6">
            <div className="flex items-center gap-2 text-sm font-bold text-[#B4F105]">
              <span className="h-2 w-2 rounded-full bg-[#B4F105] animate-pulse" /> Procesamiento activo
            </div>
            <Link to={`/jobs/${activeJobId}`} className="btn-custom btn-custom-primary btn-custom-sm">
              Ver progreso → <i className="bi bi-arrow-right" />
            </Link>
          </div>
        )}
        <div className="mb-6 sm:mb-8">
          <div className="inline-flex items-center gap-2 mb-3 px-3 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.10)] text-[#B4F105] border border-[rgba(180,241,5,0.22)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.6)] animate-pulse" /> LIVE
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: '#F1F5F9' }}>
            Dashboard de Métricas
          </h1>
          <p className="text-sm mt-2" style={{ color: '#94A3B8' }}>
            Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.
          </p>
        </div>

        <div className="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-4 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="h-9 w-9 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000]">
              <i className="bi bi-youtube" />
            </span>
            <div>
              <p className="text-sm font-bold text-white">YouTube — OAuth 2.0 (Issue #24)</p>
              <p className="text-xs text-[#94A3B8]">Prueba el conector: GET /auth/social/youtube/connect</p>
            </div>
          </div>
          <Link to="/dashboard/integrations" className="btn-custom btn-custom-primary flex items-center gap-2 whitespace-nowrap" data-testid="go-integrations">
            <i className="bi bi-box-arrow-up-right" /> Conectar YouTube
          </Link>
        </div>

        {loading && (
          <>
            <KpiSkeleton />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
              <div className="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-6 h-[320px] animate-pulse">
                <div className="h-4 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-6" />
                <div className="h-[240px] bg-[rgba(255,255,255,0.04)] rounded" />
              </div>
              <div className="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-6 h-[320px] animate-pulse">
                <div className="h-4 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-6" />
                <div className="h-[240px] bg-[rgba(255,255,255,0.04)] rounded" />
              </div>
            </div>
          </>
        )}

        {error && !loading && (
          <div role="alert" className="alert-custom alert-custom-danger">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{error}</div>
            <button onClick={fetchAll} className="btn-custom btn-custom-danger btn-custom-sm">
              Reintentar
            </button>
          </div>
        )}

        {!loading && !error && isEmpty && (
          <div className="rounded-2xl bg-[#121824] border border-dashed border-[rgba(180,241,5,0.18)] p-10 text-center shadow-xl">
            <div className="h-12 w-12 rounded-full bg-[rgba(180,241,5,0.10)] border border-[rgba(180,241,5,0.22)] flex items-center justify-center text-xl mx-auto text-[#B4F105]">📊</div>
            <p className="text-sm font-bold text-[#F1F5F9] mt-4">Aún no tienes métricas</p>
            <p className="text-xs text-[#94A3B8] mt-1 max-w-[300px] mx-auto">
              Cuando proceses tu primer video verás aquí clips generados, horas ahorradas y actividad de los últimos 7 días.
            </p>
            <Link to="/upload" className="btn-custom btn-custom-primary mt-5 shadow-[0_0_20px_rgba(180,241,5,0.3)]">
              <i className="bi bi-lightning-charge-fill" /> Subir primer video
            </Link>
          </div>
        )}

        {!loading && !error && metrics && !isEmpty && (
          <>
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
              <div className={chartCardClass}>
                <h2 className="text-sm font-semibold" style={{ color: '#f9fafb' }}>
                  {hasPlatformData ? 'Distribución por Plataforma' : 'Distribución por Score'}
                </h2>
                <p className="text-xs mt-1" style={{ color: '#d1d5db' }}>
                  {hasPlatformData ? 'Clips agrupados por red social objetivo' : 'Conteo de clips agrupados por rango de viralidad'}
                </p>
                <div className="mt-6">
                  {hasPlatformData ? (
                    <div className="space-y-4">
                      {platformEntries.map((entry) => (
                        <div key={entry.platform} className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium capitalize" style={{ color: platformColors[entry.platform] ?? '#9ca3af' }}>{entry.platform}</span>
                            <span className="text-gray-400 font-mono">{entry.count} clips</span>
                          </div>
                          <div className="h-8 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden p-1 border border-[rgba(255,255,255,0.04)]">
                            <div
                              className="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2"
                              style={{ width: `${(entry.count / maxPlatform) * 100}%`, backgroundColor: platformColors[entry.platform] ?? '#6366f1', minWidth: entry.count > 0 ? '32px' : '0' }}
                            >
                              {entry.count > 0 && <span className="text-[11px] font-bold text-white">{entry.count}</span>}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div>
                      <div className="space-y-4">
                        {(stats?.score_distribution ?? []).map((item) => (
                          <div key={item.range} className="space-y-1.5">
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-medium" style={{ color: barColors[item.label] ?? '#9ca3af' }}>{item.label} ({item.range})</span>
                              <span className="text-[#94A3B8] font-mono">{item.count} clips</span>
                            </div>
                            <div className="h-8 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden p-1 border border-[rgba(255,255,255,0.04)]">
                              <div
                                className="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2"
                                style={{ width: `${(item.count / maxCount) * 100}%`, backgroundColor: barColors[item.label] ?? '#6366f1', minWidth: item.count > 0 ? '32px' : '0' }}
                              >
                                {item.count > 0 && <span className="text-[11px] font-bold text-white">{item.count}</span>}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="flex items-center justify-center gap-4 mt-6">
                        <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#ef4444' }} /> 0-40 Bajo
                        </span>
                        <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#f59e0b' }} /> 41-70 Medio
                        </span>
                        <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#10b981' }} /> 71-100 Alto
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className={chartCardClass}>
                <h2 className="text-sm font-semibold text-white">Actividad Reciente</h2>
                <p className="text-xs mt-1" style={{ color: '#d1d5db' }}>
                  Últimos 7 días · jobs, clips y minutos procesados
                </p>
                <div className="mt-6 space-y-3">
                  {metrics.recent_activity.map((day) => (
                    <div key={day.date} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-gray-400">{day.date.slice(5)}</span>
                        <span className="text-gray-500">{day.jobs} jobs · {day.clips} clips · {day.minutes_processed} min</span>
                      </div>
                      <div className="h-8 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden p-1 flex gap-1 border border-[rgba(255,255,255,0.04)]">
                        <div
                          className="h-full rounded-full bg-violet-500 transition-all flex items-center justify-center"
                          style={{ width: `${(day.jobs / maxRecent) * 40}%`, minWidth: day.jobs > 0 ? '24px' : '0' }}
                          title={`${day.jobs} jobs`}
                        >
                          {day.jobs > 0 && <span className="text-[10px] font-bold text-white">{day.jobs}</span>}
                        </div>
                        <div
                          className="h-full rounded-full bg-emerald-500 transition-all flex items-center justify-center"
                          style={{ width: `${(day.clips / maxRecent) * 40}%`, minWidth: day.clips > 0 ? '24px' : '0' }}
                          title={`${day.clips} clips`}
                        >
                          {day.clips > 0 && <span className="text-[10px] font-bold text-white">{day.clips}</span>}
                        </div>
                        <div
                          className="h-full rounded-full bg-amber-500 transition-all flex items-center justify-center"
                          style={{ width: `${(day.minutes_processed / maxRecent) * 20}%`, minWidth: day.minutes_processed > 0 ? '24px' : '0' }}
                          title={`${day.minutes_processed} min`}
                        >
                          {day.minutes_processed > 0 && <span className="text-[10px] font-bold text-white">{day.minutes_processed}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-center gap-4 mt-6">
                  <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                    <span className="h-2.5 w-2.5 rounded-full bg-violet-500" /> Jobs
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Clips
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Min
                  </span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
