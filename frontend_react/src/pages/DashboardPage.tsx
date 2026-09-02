import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts'
import { statsService } from '@/services/api'
import type { StatsSummary } from '@/types/api'
import { ApiError } from '@/types/api'

function formatTime(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

function scoreBadge(score: number) {
  if (score >= 71) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (score >= 41) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  return 'bg-red-500/15 text-red-300 border-red-500/30'
}

function statusBadge(status: string) {
  const s = status.toUpperCase()
  if (s === 'COMPLETED') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (s === 'PROCESSING') return 'bg-sky-500/15 text-sky-300 border-sky-500/30'
  if (s === 'PENDING') return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  if (s === 'FAILED') return 'bg-red-500/15 text-red-300 border-red-500/30'
  return 'bg-gray-700 text-gray-300 border-gray-600'
}

function KpiSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5 animate-pulse">
          <div className="h-3 bg-white dark:bg-slate-800 rounded w-1/2 mb-4" />
          <div className="h-8 bg-white dark:bg-slate-800 rounded w-1/3 mb-2" />
          <div className="h-3 bg-white dark:bg-slate-800 rounded w-2/3" />
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState<StatsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    statsService
      .getSummary()
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError) setError(err.detail)
        else if (err instanceof Error) setError(err.message)
        else setError('Error al cargar estadísticas')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const chartData = data?.score_distribution.map((d) => ({
    name: d.label,
    range: d.range,
    count: d.count,
  }))

  const barColors: Record<string, string> = {
    Bajo: '#ef4444',
    Medio: '#f59e0b',
    Alto: '#10b981',
  }

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Dashboard de Métricas</h1>
          <p className="text-sm text-slate-600 mt-2">
            Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.
          </p>
        </div>

        {loading && (
          <>
            <KpiSkeleton />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-6 h-[320px] animate-pulse">
                <div className="h-4 bg-white dark:bg-slate-800 rounded w-1/3 mb-6" />
                <div className="h-[240px] bg-white dark:bg-slate-800 rounded" />
              </div>
              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-6 h-[320px] animate-pulse">
                <div className="h-4 bg-white dark:bg-slate-800 rounded w-1/3 mb-6" />
                <div className="h-20 bg-white dark:bg-slate-800 rounded" />
              </div>
            </div>
          </>
        )}

        {error && !loading && (
          <div role="alert" className="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-center">
            <p className="text-sm text-red-300">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-xl px-4 py-2 transition"
            >
              Reintentar
            </button>
          </div>
        )}

        {data && !loading && !error && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5">
                <p className="text-xs font-medium text-slate-600 uppercase tracking-wide">Total Videos Subidos</p>
                <p className="text-3xl font-bold mt-2">{data.total_videos}</p>
                <p className="text-xs text-slate-600 mt-1">Videos procesados en tu cuenta</p>
              </div>

              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5">
                <p className="text-xs font-medium text-slate-600 uppercase tracking-wide">Total Clips Generados</p>
                <p className="text-3xl font-bold mt-2">{data.total_clips}</p>
                <p className="text-xs text-slate-600 mt-1">Clips virales extraídos</p>
              </div>

              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5">
                <p className="text-xs font-medium text-slate-600 uppercase tracking-wide">Promedio de Viralidad</p>
                <div className="flex items-center gap-3 mt-2">
                  <p className="text-3xl font-bold">{data.avg_score.toFixed(1)}</p>
                  <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreBadge(data.avg_score)}`}>
                    {data.avg_score >= 71 ? 'Alto' : data.avg_score >= 41 ? 'Medio' : 'Bajo'}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-1">Score promedio de todos tus clips</p>
              </div>

              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5">
                <p className="text-xs font-medium text-slate-600 uppercase tracking-wide">Tiempo Ahorrado</p>
                <p className="text-3xl font-bold mt-2">{formatTime(data.estimated_time_saved_minutes)}</p>
                <p className="text-xs text-slate-600 mt-1">Estimado · {data.total_clips} × 15 min</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5 sm:p-6">
                <h2 className="text-sm font-semibold text-white">Distribución por Score</h2>
                <p className="text-xs text-slate-600 mt-1">Conteo de clips agrupados por rango de viralidad</p>
                <div className="h-[280px] mt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
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
                        {chartData?.map((entry, idx) => (
                          <Cell key={`cell-${idx}`} fill={barColors[entry.name] ?? '#6366f1'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex items-center justify-center gap-4 mt-2">
                  <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                    <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> 0-40 Bajo
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> 41-70 Medio
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> 71-100 Alto
                  </span>
                </div>
              </div>

              <div className="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-5 sm:p-6 flex flex-col">
                <h2 className="text-sm font-semibold text-white">Actividad Reciente</h2>
                <p className="text-xs text-slate-600 mt-1">Último job de procesamiento</p>

                {data.recent_job ? (
                  <div className="mt-6 rounded-xl bg-white dark:bg-slate-800/60 border border-slate-200/70 dark:border-slate-800 shadow-sm shadow-slate-100/80 p-4 sm:p-5 flex flex-col gap-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs text-slate-600">Job ID</p>
                        <p className="text-sm font-mono text-white truncate">{data.recent_job.id}</p>
                        <p className="text-xs text-slate-600 mt-1">
                          Creado: {new Date(data.recent_job.created_at).toLocaleString()}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${statusBadge(data.recent_job.status)}`}
                      >
                        {data.recent_job.status}
                      </span>
                    </div>
                    <Link
                      to={`/jobs/${data.recent_job.id}`}
                      className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white text-sm font-medium py-2.5 px-4 transition"
                    >
                      Ver Job →
                    </Link>
                  </div>
                ) : (
                  <div className="mt-6 flex flex-1 flex-col items-center justify-center rounded-xl bg-white dark:bg-slate-800/40 border border-dashed border-slate-200 dark:border-slate-700 p-8 text-center">
                    <div className="h-12 w-12 rounded-full bg-white dark:bg-slate-800 flex items-center justify-center text-xl">🎬</div>
                    <p className="text-sm font-medium text-gray-200 mt-4">Aún no hay actividad</p>
                    <p className="text-xs text-slate-600 mt-1 max-w-[260px]">
                      Sube tu primer video para generar clips y ver métricas aquí.
                    </p>
                    <Link
                      to="/upload"
                      className="mt-5 inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white text-sm font-medium py-2.5 px-5 transition"
                    >
                      Subir primer video
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
