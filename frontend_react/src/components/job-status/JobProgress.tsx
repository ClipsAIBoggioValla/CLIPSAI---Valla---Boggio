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
        <div className="space-y-2 rounded-xl px-4 py-4 border" style={{ backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>
          <div className="flex justify-between items-center text-xs font-bold">
            <span style={{ color: 'var(--text-muted-green)' }}>{job.status.toUpperCase() === 'PENDING' ? 'En cola...' : `Procesando... ${job.progress ?? 0}%`}</span>
            <span style={{ color: 'var(--text-main)' }}>{job.progress ?? 0}%</span>
          </div>
          <div className="w-full rounded-full h-2.5 overflow-hidden border" style={{ backgroundColor: 'rgba(0,0,0,0.2)', borderColor: 'var(--border-light)' }}>
            <div className="h-2.5 rounded-full transition-all duration-500 ease-out" style={{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%`, backgroundColor: '#B4F105', boxShadow: '0 0 8px rgba(180,241,5,0.4)' }} />
          </div>
          <p className="text-[11px] text-center font-medium" style={{ color: 'var(--text-muted-green)' }}>
            {(job.progress ?? 0) === 10 && 'Extrayendo y transcribiendo audio con Whisper...'}
            {(job.progress ?? 0) === 35 && 'Transcripción (Whisper) completada...'}
            {(job.progress ?? 0) === 65 && 'Análisis de hooks (Claude) completado...'}
            {(job.progress ?? 0) >= 70 && (job.progress ?? 0) < 90 && 'Renderizando clips...'}
            {(job.progress ?? 0) >= 90 && (job.progress ?? 0) < 100 && 'Finalizando renderizado...'}
            {(job.progress ?? 0) === 0 && 'Esperando en cola...'}
            {(job.progress ?? 0) > 35 && (job.progress ?? 0) < 65 && 'Analizando contenido viral...'}
          </p>
        </div>
      )}
      {job.status.toUpperCase() === 'PENDING' && (
        <div className="alert-custom alert-custom-warning">
          <i className="bi bi-hourglass-split alert-custom-icon" />
          <div className="alert-custom-content"><strong>En cola...</strong> Tu video está esperando a ser procesado. Esto se actualiza solo.</div>
        </div>
      )}
      {job.status.toUpperCase() === 'PROCESSING' && (
        <div className="alert-custom alert-custom-info">
          <i className="bi bi-arrow-repeat alert-custom-icon" style={{ animation: 'spin 1s linear infinite' }} />
          <div className="alert-custom-content"><strong>Procesando video y generando clips...</strong> Puede tardar unos minutos. La página se actualiza automáticamente.</div>
        </div>
      )}
    </>
  )
}
