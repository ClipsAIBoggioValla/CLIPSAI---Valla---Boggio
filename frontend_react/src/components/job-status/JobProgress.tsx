import type { JobResponse } from '@/types/api'

interface JobProgressProps {
  job: JobResponse | null
}

export default function JobProgress(props: JobProgressProps) {
  const { job } = props
  if (!job) return null
  return (
    <>
      {(job.status.toUpperCase() === 'PROCESSING' || job.status.toUpperCase() === 'PENDING') && (
        <div className="card-spark !p-4 space-y-2">
          <div className="flex justify-between items-center text-xs font-bold">
            <span className="text-[var(--text-secondary)]">{job.status.toUpperCase() === 'PENDING' ? 'En espera...' : `Creando tus clips... ${job.progress ?? 0}%`}</span>
            <span className="text-[var(--text-primary)]">{job.progress ?? 0}%</span>
          </div>
          <div className="w-full rounded-full h-2.5 overflow-hidden border border-[var(--border-subtle)] bg-white/5">
            <div className="h-2.5 rounded-full bg-[var(--brand-lime)] shadow-[var(--brand-lime-glow)] transition-all duration-500 ease-out" style={{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%` }} />
          </div>
          <p className="text-[11px] text-center font-medium text-[var(--text-secondary)]">
            {(job.progress ?? 0) === 10 && 'Preparando el texto de tu video...'}
            {(job.progress ?? 0) === 35 && 'Texto del video listo...'}
            {(job.progress ?? 0) === 65 && 'Momentos destacados identificados...'}
            {(job.progress ?? 0) >= 70 && (job.progress ?? 0) < 90 && 'Creando tus clips...'}
            {(job.progress ?? 0) >= 90 && (job.progress ?? 0) < 100 && 'Dando los últimos toques a tus clips...'}
            {(job.progress ?? 0) === 0 && 'Tu video está en la fila...'}
            {(job.progress ?? 0) > 35 && (job.progress ?? 0) < 65 && 'Buscando momentos destacados...'}
          </p>
        </div>
      )}
      {job.status.toUpperCase() === 'PENDING' && (
        <div className="alert-custom alert-custom-warning">
          <i className="bi bi-hourglass-split alert-custom-icon" />
          <div className="alert-custom-content"><strong>Enseguida comenzamos...</strong> Tu video está esperando su turno. El progreso se actualiza solo.</div>
        </div>
      )}
      {job.status.toUpperCase() === 'PROCESSING' && (
        <div className="alert-custom alert-custom-info">
          <i className="bi bi-arrow-repeat alert-custom-icon animate-spin" />
          <div className="alert-custom-content"><strong>Creando tus clips...</strong> Puede tardar unos minutos. El progreso se actualiza automáticamente.</div>
        </div>
      )}
    </>
  )
}
