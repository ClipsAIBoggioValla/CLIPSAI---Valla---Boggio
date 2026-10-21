import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { metricsService, statsService } from '@/services/api'
import type { MetricsResponse, StatsSummary } from '@/types/api'
import { ApiError } from '@/types/api'
import DashboardContent from '@/components/dashboard/DashboardContent'
import { KpiSkeleton } from '@/components/dashboard/KpiSkeleton'

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
    setLoading(true); setError(null)
    try {
      const [s, m] = await Promise.all([statsService.getSummary(), metricsService.getMetrics()])
      setStats(s); setMetrics(m)
    } catch (err: unknown) {
      if (err instanceof ApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError('Error al cargar métricas')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (!loading) return
    const t = window.setTimeout(() => setLoading(false), 5000)
    return () => window.clearTimeout(t)
  }, [loading])

  const isEmpty = metrics && metrics.total_jobs === 0 && metrics.total_clips === 0

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
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: '#F1F5F9' }}>Dashboard de Métricas</h1>
          <p className="text-sm mt-2" style={{ color: '#94A3B8' }}>Visualiza el rendimiento de tus videos, clips generados y tiempo ahorrado gracias a la automatización.</p>
        </div>

        <div className="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-4 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="h-9 w-9 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000]"><i className="bi bi-youtube" /></span>
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
            <button onClick={fetchAll} className="btn-custom btn-custom-danger btn-custom-sm">Reintentar</button>
          </div>
        )}

        {!loading && !error && isEmpty && (
          <div className="rounded-2xl bg-[#121824] border border-dashed border-[rgba(180,241,5,0.18)] p-10 text-center shadow-xl">
            <div className="h-12 w-12 rounded-full bg-[rgba(180,241,5,0.10)] border border-[rgba(180,241,5,0.22)] flex items-center justify-center text-xl mx-auto text-[#B4F105]">📊</div>
            <p className="text-sm font-bold text-[#F1F5F9] mt-4">Aún no tienes métricas</p>
            <p className="text-xs text-[#94A3B8] mt-1 max-w-[300px] mx-auto">Cuando proceses tu primer video verás aquí clips generados, horas ahorradas y actividad de los últimos 7 días.</p>
            <Link to="/upload" className="btn-custom btn-custom-primary mt-5 shadow-[0_0_20px_rgba(180,241,5,0.3)]">
              <i className="bi bi-lightning-charge-fill" /> Subir primer video
            </Link>
          </div>
        )}

        {!loading && !error && metrics && !isEmpty && (
          <DashboardContent stats={stats} metrics={metrics} />
        )}
      </div>
    </div>
  )
}
