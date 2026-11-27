interface DirectUploadPanelProps {
  videoFile: File | null
  directUploadState: 'idle' | 'uploading' | 'processing' | 'success' | 'error'
  directUploadError: string | null
  directUploadKey: string | null
  directUploadResult: { clip_count?: number; clips?: Array<{ start_time?: string | number; inicio?: string | number; end_time?: string | number; fin?: string | number; score?: number; title?: string; titulo_sugerido?: string; titulo?: string }>; engine?: string } | null
  isUploading: boolean
  onUpload: (file: File) => void
}

export default function DirectUploadPanel(props: DirectUploadPanelProps) {
  const { videoFile, directUploadState, directUploadError, directUploadKey, directUploadResult, isUploading, onUpload } = props
  const isBusy = directUploadState === 'uploading' || directUploadState === 'processing'
  return (
    <div className="card-spark space-y-4">
      <div>
        <p className="text-sm font-bold text-[var(--text-primary)]">Encuentra momentos para tus próximos clips</p>
        <p className="text-xs mt-1 text-[var(--text-secondary)]">Sube tu video y la IA buscará momentos destacados para convertirlos en clips.</p>
      </div>
      <button type="button" onClick={() => videoFile && void onUpload(videoFile)} disabled={!videoFile || isBusy || isUploading} className="btn-custom btn-custom-light w-full justify-center disabled:opacity-50">
        {isBusy ? (
          <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[var(--brand-lime)]" /> {directUploadState === 'uploading' ? 'Subiendo tu video...' : 'Buscando momentos destacados...'}</>
        ) : directUploadState === 'success' ? (
          <><i className="bi bi-check-circle-fill text-emerald-400" /> Análisis completado</>
        ) : (
          <><i className="bi bi-cloud-arrow-up" /> Subir y encontrar clips</>
        )}
      </button>
      {(directUploadState === 'uploading' || directUploadState === 'processing') && (
        <div role="status" className="space-y-2">
          <div className="progress"><div className="progress-bar w-full animate-pulse" style={{ height: '8px', borderRadius: '50rem' }} /></div>
          <p className="text-xs text-center text-[var(--text-secondary)]">{directUploadState === 'uploading' ? 'Estamos preparando tu video...' : 'Estamos buscando momentos que puedas convertir en clips.'}</p>
        </div>
      )}
      {directUploadState === 'success' && directUploadKey && (
        <div role="status" className="alert-custom alert-custom-success flex-col items-start">
          <p className="text-sm font-semibold">¡Tu video ya está listo!</p>
          <p className="text-xs text-[var(--text-primary)]">Encontramos {directUploadResult?.clip_count ?? directUploadResult?.clips?.length ?? 0} clips para ti.</p>
          {directUploadResult?.clips?.length ? (
            <ul className="space-y-2">
              {directUploadResult.clips.map((clip, index) => (
                <li key={`${clip.start_time ?? clip.inicio ?? index}-${index}`} className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{clip.title ?? clip.titulo_sugerido ?? clip.titulo ?? `Clip ${index + 1}`}</p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {String(clip.start_time ?? clip.inicio ?? '—')} – {String(clip.end_time ?? clip.fin ?? '—')}
                    {clip.score !== undefined ? ` · Potencial ${clip.score}/100` : ''}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">Esta vez no encontramos clips para este video. Prueba con otro.</p>
          )}
        </div>
      )}
      {directUploadState === 'error' && directUploadError && (
        <p role="alert" className="alert-custom alert-custom-danger">{directUploadError}</p>
      )}
    </div>
  )
}
