import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell, Legend } from 'recharts'
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

  const scoreChartData = stats?.score_distribution.map((d) => ({
    name: d.label,
    range: d.range,
    count: d.count,
  }))

  const barColors: Record<string, string> = {
    Bajo: '#ef4444',
    Medio: '#f59e0b',
    Alto: '#10b981',
  }

  const platformData = metrics
    ? Object.entries(metrics.platform_distribution).map(([platform, count]) => ({
        platform: platform.charAt(0).toUpperCase() + platform.slice(1),
        count,
      }))
    : []

  const hasPlatformData = platformData.some((d) => d.count > 0)

  const platformColors: Record<string, string> = {
    Tiktok: '#EC4899',
    Youtube: '#EF4444',
    Instagram: '#8B5CF6',
  }

  const recentData = metrics?.recent_activity.map((d) => ({
    date: d.date.slice(5),
    jobs: d.jobs,
    clips: d.clips,
    minutos: d.minutes_processed,
  }))

  const isEmpty = metrics && metrics.total_jobs === 0 && metrics.total_clips === 0

  const chartCardClass = 'rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 sm:p-6 shadow-xl'

  return (
    <div className="min-h-screen bg-[#0B0F17] text-white">
      <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
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
                <div className="h-[280px] mt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    {hasPlatformData ? (
                      <BarChart data={platformData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey="platform" stroke="#e5e7eb" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#e5e7eb" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #4b5563', borderRadius: '12px' }}
                          labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
                          itemStyle={{ color: '#f3f4f6' }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px', color: '#e5e7eb' }} />
                        <Bar dataKey="count" name="Clips" radius={[8, 8, 0, 0]} barSize={48}>
                          {platformData.map((entry, idx) => (
                            <Cell key={`cell-${idx}`} fill={platformColors[entry.platform] ?? '#6366f1'} />
                          ))}
                        </Bar>
                      </BarChart>
                    ) : (
                      <BarChart data={scoreChartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey="name" stroke="#e5e7eb" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#e5e7eb" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #4b5563', borderRadius: '12px' }}
                          labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
                          itemStyle={{ color: '#f3f4f6' }}
                          formatter={(value, _name, item) => {
                            const range = (item as unknown as { payload: { range: string } }).payload?.range ?? ''
                            return [`${value ?? 0} clips`, `Rango ${range}`]
                          }}
                        />
                        <Bar dataKey="count" radius={[8, 8, 0, 0]} barSize={48}>
                          {scoreChartData?.map((entry, idx) => (
                            <Cell key={`cell-${idx}`} fill={barColors[entry.name] ?? '#6366f1'} />
                          ))}
                        </Bar>
                      </BarChart>
                    )}
                  </ResponsiveContainer>
                </div>
                {!hasPlatformData && (
                  <div className="flex items-center justify-center gap-4 mt-2">
                    <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                      <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> 0-40 Bajo
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                      <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> 41-70 Medio
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                      <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> 71-100 Alto
                    </span>
                  </div>
                )}
              </div>

              <div className={chartCardClass}>
                <h2 className="text-sm font-semibold text-white">Actividad Reciente</h2>
                <p className="text-xs mt-1" style={{ color: '#d1d5db' }}>
                  Últimos 7 días · jobs, clips y minutos procesados
                </p>
                <div className="h-[280px] mt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={recentData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="date" stroke="#e5e7eb" fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis stroke="#e5e7eb" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #4b5563', borderRadius: '12px' }}
                        labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
                        itemStyle={{ color: '#f3f4f6' }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', color: '#e5e7eb' }} />
                      <Bar dataKey="jobs" name="Jobs" fill="#8b5cf6" radius={[6, 6, 0, 0]} barSize={14} />
                      <Bar dataKey="clips" name="Clips" fill="#10b981" radius={[6, 6, 0, 0]} barSize={14} />
                      <Bar dataKey="minutos" name="Minutos" fill="#f59e0b" radius={[6, 6, 0, 0]} barSize={14} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
