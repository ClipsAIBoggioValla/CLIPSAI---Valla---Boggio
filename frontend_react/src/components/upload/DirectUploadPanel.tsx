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
    <div className="rounded-xl border border-white/10 bg-[#0B0F17] p-4 space-y-3">
      <div>
        <p className="text-sm font-bold text-[#F1F5F9]">Subida directa a Cloudflare R2</p>
        <p className="text-xs mt-1 text-[#94A3B8]">Sube el video a R2 y envía su URL prefirmada al worker de RunPod.</p>
      </div>
      <button type="button" onClick={() => videoFile && void onUpload(videoFile)} disabled={!videoFile || isBusy || isUploading} className="btn-custom btn-custom-light w-full justify-center disabled:opacity-50">
        {isBusy ? (
          <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" /> {directUploadState === 'uploading' ? 'Subiendo a R2...' : 'Procesando con RunPod...'}</>
        ) : directUploadState === 'success' ? (
          <><i className="bi bi-check-circle-fill text-emerald-400" /> Procesamiento completado</>
        ) : (
          <><i className="bi bi-cloud-arrow-up" /> Subir video directamente a R2</>
        )}
      </button>
      {(directUploadState === 'uploading' || directUploadState === 'processing') && (
        <div role="status" className="space-y-2">
          <div className="progress"><div className="progress-bar w-full animate-pulse" style={{ height: '8px', borderRadius: '50rem' }} /></div>
          <p className="text-xs text-center text-[#94A3B8]">{directUploadState === 'uploading' ? 'Transfiriendo archivo directamente al storage...' : 'RunPod está analizando el video y buscando clips...'}</p>
        </div>
      )}
      {directUploadState === 'success' && directUploadKey && (
        <div role="status" className="space-y-2">
          <p className="text-xs text-emerald-400 break-all">Archivo procesado. Clave R2: {directUploadKey}</p>
          <p className="text-xs text-[#CBD5E1]">{directUploadResult?.clip_count ?? directUploadResult?.clips?.length ?? 0} clips devueltos · motor {directUploadResult?.engine ?? 'ClipsAI'}</p>
          {directUploadResult?.clips?.length ? (
            <ul className="space-y-2">
              {directUploadResult.clips.map((clip, index) => (
                <li key={`${clip.start_time ?? clip.inicio ?? index}-${index}`} className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                  <p className="text-sm font-semibold text-[#F1F5F9]">{clip.title ?? clip.titulo_sugerido ?? clip.titulo ?? `Clip ${index + 1}`}</p>
                  <p className="text-xs text-[#94A3B8]">
                    {String(clip.start_time ?? clip.inicio ?? '—')} – {String(clip.end_time ?? clip.fin ?? '—')}
                    {clip.score !== undefined ? ` · Score ${clip.score}` : ''}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[#94A3B8]">El worker no devolvió clips para este video.</p>
          )}
        </div>
      )}
      {directUploadState === 'error' && directUploadError && (
        <p role="alert" className="text-xs text-red-400">{directUploadError}</p>
      )}
    </div>
  )
}
