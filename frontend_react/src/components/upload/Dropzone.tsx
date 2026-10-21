interface DropzoneProps {
  videoFile: File | null
  onVideoChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  sampleState: 'idle' | 'loading' | 'success' | 'error'
  sampleError: string | null
  isUploading: boolean
  isDirectUploadBusy: boolean
  isSampleBusy: boolean
  onSampleJob: () => void
}

export default function Dropzone(props: DropzoneProps) {
  const { videoFile, onVideoChange, sampleState, sampleError, isUploading, isDirectUploadBusy, isSampleBusy, onSampleJob } = props
  return (
    <>
      <label className={`dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer ${videoFile ? 'has-file' : ''}`}>
        <span className="dropzone-icon-neon mb-3"><i className="bi bi-camera-video" /></span>
        <span className="text-sm font-bold" style={{ color: '#F1F5F9' }}>
          {videoFile ? videoFile.name : 'Arrastra o selecciona tu video'}
        </span>
        <span className="text-xs mt-1" style={{ color: '#94A3B8' }}>.mp4, .mov, .avi (máx. 500MB)</span>
        {videoFile && (
          <span className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]">
            <i className="bi bi-check-circle-fill" /> {(videoFile.size / 1024 / 1024).toFixed(1)} MB
          </span>
        )}
        <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" onChange={onVideoChange} className="hidden" disabled={isUploading || isDirectUploadBusy || isSampleBusy} />
      </label>
      <div className="mt-3">
        <button type="button" onClick={onSampleJob} disabled={isUploading || isDirectUploadBusy || isSampleBusy} className="btn-custom btn-custom-light w-full justify-center disabled:opacity-50">
          {sampleState === 'loading' ? (
            <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" /> Preparando video de muestra...</>
          ) : (
            <><i className="bi bi-play-circle" /> Probar con video de muestra</>
          )}
        </button>
        {sampleState === 'error' && sampleError && (
          <p role="alert" className="text-xs text-red-400 mt-2">{sampleError}</p>
        )}
        <p className="text-xs text-[#94A3B8] mt-2 text-center">Usa un clip liviano de ejemplo para evaluar el flujo completo sin subir archivos pesados.</p>
      </div>
    </>
  )
}
