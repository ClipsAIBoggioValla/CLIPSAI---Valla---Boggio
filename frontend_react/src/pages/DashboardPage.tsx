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
        <div key={i} className="rounded-2xl bg-gray-900 border border-gray-800 p-5 animate-pulse">
          <div className="h-3 bg-gray-800 rounded w-1/2 mb-4" />
          <div className="h-8 bg-gray-800 rounded w-1/3 mb-2" />
          <div className="h-3 bg-gray-800 rounded w-2/3" />
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

  const chartCardClass = 'rounded-2xl bg-gray-900 border border-gray-800 p-5 sm:p-6'

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Dashboard de Métricas</h1>
          <p className="text-sm text-gray-400 mt-2">
            Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.
          </p>
        </div>

        {loading && (
          <>
            <KpiSkeleton />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
              <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 h-[320px] animate-pulse">
                <div className="h-4 bg-gray-800 rounded w-1/3 mb-6" />
                <div className="h-[240px] bg-gray-800 rounded" />
              </div>
              <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 h-[320px] animate-pulse">
                <div className="h-4 bg-gray-800 rounded w-1/3 mb-6" />
                <div className="h-[240px] bg-gray-800 rounded" />
              </div>
            </div>
          </>
        )}

        {error && !loading && (
          <div role="alert" className="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-center">
            <p className="text-sm text-red-300">{error}</p>
            <button
              onClick={fetchAll}
              className="mt-4 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-xl px-4 py-2 transition"
            >
              Reintentar
            </button>
          </div>
        )}

        {!loading && !error && isEmpty && (
          <div className="rounded-2xl bg-gray-900 border border-dashed border-gray-700 p-10 text-center">
            <div className="h-12 w-12 rounded-full bg-gray-800 flex items-center justify-center text-xl mx-auto">📊</div>
            <p className="text-sm font-medium text-gray-200 mt-4">Aún no tienes métricas</p>
            <p className="text-xs text-gray-500 mt-1 max-w-[300px] mx-auto">
              Cuando proceses tu primer video verás aquí clips generados, horas ahorradas y actividad de los últimos 7 días.
            </p>
            <Link
              to="/upload"
              className="mt-5 inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium py-2.5 px-5 transition"
            >
              Subir primer video
            </Link>
          </div>
        )}

        {!loading && !error && metrics && !isEmpty && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded-2xl bg-gray-900 border border-gray-800 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Videos / Jobs</p>
                <p className="text-3xl font-bold mt-2">{metrics.total_jobs}</p>
                <p className="text-xs text-gray-500 mt-1">{stats ? `${stats.total_videos} videos subidos` : 'Jobs procesados'}</p>
              </div>

              <div className="rounded-2xl bg-gray-900 border border-gray-800 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Clips Generados</p>
                <p className="text-3xl font-bold mt-2">{metrics.total_clips}</p>
                <p className="text-xs text-gray-500 mt-1">Clips virales extraídos</p>
              </div>

              <div className="rounded-2xl bg-gray-900 border border-gray-800 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Tiempo Ahorrado</p>
                <p className="text-3xl font-bold mt-2">{formatHours(metrics.time_saved_hours)}</p>
                <p className="text-xs text-gray-500 mt-1">Estimado · {metrics.total_minutes_processed} min procesados</p>
              </div>

              <div className="rounded-2xl bg-gray-900 border border-gray-800 p-5">
                {stats ? (
                  <>
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Promedio de Viralidad</p>
                    <div className="flex items-center gap-3 mt-2">
                      <p className="text-3xl font-bold">{stats.avg_score.toFixed(1)}</p>
                      <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreBadge(stats.avg_score)}`}>
                        {stats.avg_score >= 71 ? 'Alto' : stats.avg_score >= 41 ? 'Medio' : 'Bajo'}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Score promedio de tus clips</p>
                  </>
                ) : (
                  <>
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Minutos Procesados</p>
                    <p className="text-3xl font-bold mt-2">{metrics.total_minutes_processed}</p>
                    <p className="text-xs text-gray-500 mt-1">Acumulado total</p>
                  </>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
              <div className={chartCardClass}>
                <h2 className="text-sm font-semibold text-white">
                  {hasPlatformData ? 'Distribución por Plataforma' : 'Distribución por Score'}
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  {hasPlatformData ? 'Clips agrupados por red social objetivo' : 'Conteo de clips agrupados por rango de viralidad'}
                </p>
                <div className="h-[280px] mt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    {hasPlatformData ? (
                      <BarChart data={platformData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                        <XAxis dataKey="platform" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px' }} labelStyle={{ color: '#e5e7eb' }} />
                        <Legend wrapperStyle={{ fontSize: '12px', color: '#9ca3af' }} />
                        <Bar dataKey="count" name="Clips" radius={[8, 8, 0, 0]} barSize={48}>
                          {platformData.map((entry, idx) => (
                            <Cell key={`cell-${idx}`} fill={platformColors[entry.platform] ?? '#6366f1'} />
                          ))}
                        </Bar>
                      </BarChart>
                    ) : (
                      <BarChart data={scoreChartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                        <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px' }}
                          labelStyle={{ color: '#e5e7eb' }}
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
                <p className="text-xs text-gray-500 mt-1">Últimos 7 días · jobs, clips y minutos procesados</p>
                <div className="h-[280px] mt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={recentData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis dataKey="date" stroke="#9ca3af" fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px' }} labelStyle={{ color: '#e5e7eb' }} />
                      <Legend wrapperStyle={{ fontSize: '11px', color: '#9ca3af' }} />
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
