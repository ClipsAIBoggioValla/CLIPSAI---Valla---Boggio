import type { MetricsResponse, StatsSummary } from '@/types/api'
import KpiGrid from './KpiGrid'

interface DashboardContentProps {
  stats: StatsSummary | null
  metrics: MetricsResponse
}

interface PlatformDisplay {
  label: string
  labelClass: string
  barClass: string
}

const PLATFORM_DISPLAY: Record<string, PlatformDisplay> = {
  tiktok: { label: 'TikTok', labelClass: 'text-pink-500', barClass: 'bg-pink-500' },
  youtube: { label: 'YouTube', labelClass: 'text-red-500', barClass: 'bg-red-500' },
  instagram: { label: 'Instagram', labelClass: 'text-violet-500', barClass: 'bg-violet-500' },
}

const SCORE_COLORS: Record<string, { labelClass: string; barClass: string }> = {
  Bajo: { labelClass: 'text-red-400', barClass: 'bg-red-500' },
  Medio: { labelClass: 'text-amber-400', barClass: 'bg-amber-500' },
  Alto: { labelClass: 'text-emerald-400', barClass: 'bg-emerald-500' },
}

function getPlatformDisplay(platform: string): PlatformDisplay {
  const key = platform.toLowerCase()
  return PLATFORM_DISPLAY[key] ?? {
    label: platform.charAt(0).toUpperCase() + platform.slice(1),
    labelClass: 'text-gray-400',
    barClass: 'bg-gray-500',
  }
}

export default function DashboardContent(props: DashboardContentProps) {
  const { stats, metrics } = props
  const platformData = Object.entries(metrics.platform_distribution).map(([platform, count]) => ({
    ...getPlatformDisplay(platform),
    count,
  }))
  const hasPlatformData = platformData.some((d) => d.count > 0)
  const maxPlatform = platformData.length ? Math.max(1, ...platformData.map((e) => e.count)) : 1
  const maxCount = stats ? Math.max(1, ...stats.score_distribution.map((d) => d.count)) : 1
  const maxRecent = Math.max(1, ...metrics.recent_activity.map((d) => Math.max(d.jobs, d.clips, d.minutes_processed)))
  const recentData = metrics.recent_activity.map((d) => ({ date: d.date.slice(5), jobs: d.jobs, clips: d.clips, minutos: d.minutes_processed }))

  return (
    <>
      <KpiGrid stats={stats} metrics={metrics} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mt-6">
        <div className="card-spark p-5 sm:p-6">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{hasPlatformData ? 'Distribución por Plataforma' : 'Distribución por potencial viral'}</h2>
          <p className="text-xs mt-1 text-[var(--text-secondary)]">{hasPlatformData ? 'Clips agrupados por red social objetivo' : 'Conteo de clips agrupados por rango de viralidad'}</p>
          <div className="mt-6 space-y-4">
            {hasPlatformData ? (
              platformData.map((entry) => (
                <div key={entry.label} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-medium capitalize ${entry.labelClass}`}>{entry.label}</span>
                    <span className="text-gray-400 font-mono">{entry.count} clips</span>
                  </div>
                  <div className="h-8 rounded-full overflow-hidden bg-white/5 p-1 border border-white/5">
                    <div className={`h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2 ${entry.barClass}`} style={{ width: `${(entry.count / maxPlatform) * 100}%`, minWidth: entry.count > 0 ? '32px' : '0' }}>
                      {entry.count > 0 && <span className="text-[11px] font-bold text-white">{entry.count}</span>}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              (stats?.score_distribution ?? []).map((item) => (
                <div key={item.range} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-medium ${SCORE_COLORS[item.label]?.labelClass ?? 'text-gray-400'}`}>{item.label} ({item.range})</span>
                    <span className="text-[var(--text-secondary)] font-mono">{item.count} clips</span>
                  </div>
                  <div className="h-8 rounded-full overflow-hidden bg-white/5 p-1 border border-white/5">
                    <div className={`h-full rounded-full transition-all duration-700 flex items-center justify-end pr-2 ${SCORE_COLORS[item.label]?.barClass ?? 'bg-indigo-500'}`} style={{ width: `${(item.count / maxCount) * 100}%`, minWidth: item.count > 0 ? '32px' : '0' }}>
                      {item.count > 0 && <span className="text-[11px] font-bold text-white">{item.count}</span>}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          {!hasPlatformData && (
            <div className="flex items-center justify-center gap-4 mt-6">
              <span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><span className="h-2.5 w-2.5 rounded-full bg-red-500" /> 0-40 Bajo</span>
              <span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> 41-70 Medio</span>
              <span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> 71-100 Alto</span>
            </div>
          )}
        </div>

        <div className="card-spark p-5 sm:p-6">
          <h2 className="text-sm font-semibold text-white">Actividad Reciente</h2>
          <p className="text-xs mt-1 text-[var(--text-secondary)]">Últimos 7 días · procesos, clips y minutos procesados</p>
          <div className="mt-6 space-y-3">
            {recentData.map((day) => (
              <div key={day.date} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono text-gray-400">{day.date}</span>
                  <span className="text-gray-500">{day.jobs} procesos · {day.clips} clips · {day.minutos} min</span>
                </div>
                <div className="h-8 rounded-full overflow-hidden bg-white/5 p-1 flex gap-1 border border-white/5">
                  <div className="h-full rounded-full bg-violet-500 transition-all flex items-center justify-center" style={{ width: `${(day.jobs / maxRecent) * 40}%`, minWidth: day.jobs > 0 ? '24px' : '0' }} title={`${day.jobs} procesos`}>
                    {day.jobs > 0 && <span className="text-[10px] font-bold text-white">{day.jobs}</span>}
                  </div>
                  <div className="h-full rounded-full bg-emerald-500 transition-all flex items-center justify-center" style={{ width: `${(day.clips / maxRecent) * 40}%`, minWidth: day.clips > 0 ? '24px' : '0' }} title={`${day.clips} clips`}>
                    {day.clips > 0 && <span className="text-[10px] font-bold text-white">{day.clips}</span>}
                  </div>
                  <div className="h-full rounded-full bg-amber-500 transition-all flex items-center justify-center" style={{ width: `${(day.minutos / maxRecent) * 20}%`, minWidth: day.minutos > 0 ? '24px' : '0' }} title={`${day.minutos} min`}>
                    {day.minutos > 0 && <span className="text-[10px] font-bold text-white">{day.minutos}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-center gap-4 mt-6">
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><span className="h-2.5 w-2.5 rounded-full bg-violet-500" /> Procesos</span>
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Clips</span>
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Min</span>
          </div>
        </div>
      </div>
    </>
  )
}
