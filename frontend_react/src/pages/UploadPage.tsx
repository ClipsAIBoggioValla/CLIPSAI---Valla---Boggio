import { useState, type ChangeEvent, type FormEvent, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { jobService, videoService } from '@/services/api'
import { ApiError, type RunPodProcessResponse } from '@/types/api'

type UploadState = 'idle' | 'uploading' | 'creating_job'
type DirectUploadState = 'idle' | 'uploading' | 'processing' | 'success' | 'error'
type SampleState = 'idle' | 'loading' | 'error'

function fileErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail
  if (err instanceof Error) return err.message
  return 'Error inesperado durante la subida.'
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null)
  const [status, setStatus] = useState<UploadState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [directUploadState, setDirectUploadState] = useState<DirectUploadState>('idle')
  const [directUploadError, setDirectUploadError] = useState<string | null>(null)
  const [directUploadKey, setDirectUploadKey] = useState<string | null>(null)
  const [directUploadResult, setDirectUploadResult] = useState<RunPodProcessResponse | null>(null)
  const [sampleState, setSampleState] = useState<SampleState>('idle')
  const [sampleError, setSampleError] = useState<string | null>(null)

  useEffect(() => {
    try {
      const id = localStorage.getItem('clipsai_active_job_id')
      if (id) setActiveJobId(id)
    } catch {}
  }, [])

  const isUploading = status === 'uploading' || status === 'creating_job'
  const isDirectUploadBusy = directUploadState === 'uploading' || directUploadState === 'processing'
  const isSampleBusy = sampleState === 'loading'

  function onVideoChange(e: ChangeEvent<HTMLInputElement>) {
    setVideoFile(e.target.files?.[0] ?? null)
    setDirectUploadState('idle')
    setDirectUploadError(null)
    setDirectUploadKey(null)
    setDirectUploadResult(null)
  }
  function onTranscriptChange(e: ChangeEvent<HTMLInputElement>) {
    setTranscriptFile(e.target.files?.[0] ?? null)
  }

  async function handleFileUpload(file: File) {
    setDirectUploadState('uploading')
    setDirectUploadError(null)
    setDirectUploadKey(null)
    setDirectUploadResult(null)
    try {
      const result = await videoService.uploadDirectToStorage(file)
      setDirectUploadKey(result.file_key)
      setDirectUploadState('processing')
      const processResult = await videoService.processDirectUpload(result.file_key)
      setDirectUploadResult(processResult)
      setDirectUploadState('success')
    } catch (err: unknown) {
      setDirectUploadError(fileErrorMessage(err))
      setDirectUploadState('error')
    }
  }

  /** Issue 34: iniciar job con video de muestra sin subir archivo. */
  async function handleSampleJob() {
    setSampleState('loading')
    setSampleError(null)
    try {
      const job = await videoService.createSampleJob()
      const jobId = job.job_id ?? job.id
      try {
        localStorage.setItem('clipsai_active_job_id', jobId)
      } catch {}
      navigate(`/jobs/${jobId}`, { replace: false })
    } catch (err: unknown) {
      setSampleError(fileErrorMessage(err))
      setSampleState('error')
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!videoFile) {
      setError('Selecciona el archivo de video.')
      return
    }
    setError(null)
    try {
      setStatus('uploading')
      const video = await videoService.upload(videoFile, transcriptFile ?? null)
      setStatus('creating_job')
      const job = await jobService.createJob(video.id)
      const jobId = job.job_id ?? job.id
      try {
        localStorage.setItem('clipsai_active_job_id', jobId)
      } catch {}
      navigate(`/jobs/${jobId}`, { replace: false })
    } catch (err: unknown) {
      setStatus('idle')
      setError(fileErrorMessage(err))
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      {activeJobId && (
        <div className="rounded-xl border border-[rgba(180,241,5,0.22)] bg-[rgba(180,241,5,0.08)] px-4 py-3 flex items-center justify-between gap-3 mb-6">
          <span className="text-sm font-bold text-[#B4F105] flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#B4F105] animate-pulse" /> Procesamiento activo detectado
          </span>
          <Link to={`/jobs/${activeJobId}`} className="btn-custom btn-custom-primary btn-custom-sm">
            Ver progreso {activeJobId.slice(0, 8)} →
          </Link>
        </div>
      )}
      <div className="page-header" style={{ marginBottom: '2rem' }}>
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]">
              <i className="bi bi-cloud-arrow-up" style={{ fontSize: '1.15rem' }} />
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]">
              <i className="bi bi-stars" /> Nuevo
            </span>
          </div>
          <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.25rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>
            Subir video
          </h1>
          <p className="page-subtitle" style={{ marginBottom: 0, marginTop: '0.7rem', fontSize: '0.92rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6, maxWidth: '640px' }}>
            Sube tu video y su transcripción para generar clips automáticamente con IA.
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" className="alert-custom alert-custom-danger">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content">{error}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="card-spark space-y-6">
        <div>
          <label className="form-label-custom">
            Archivo de Video <span className="text-[#B4F105]">*</span>
          </label>
          <label className={`dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer ${videoFile ? 'has-file' : ''}`}>
            <span className="dropzone-icon-neon mb-3"><i className="bi bi-camera-video" /></span>
            <span className="text-sm font-bold" style={{ color: '#F1F5F9' }}>
              {videoFile ? videoFile.name : 'Arrastra o selecciona tu video'}
            </span>
            <span className="text-xs mt-1" style={{ color: '#94A3B8' }}>
              .mp4, .mov, .avi (máx. 500MB)
            </span>
            {videoFile && (
              <span className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]">
                <i className="bi bi-check-circle-fill" /> {(videoFile.size / 1024 / 1024).toFixed(1)} MB
              </span>
            )}
            <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" onChange={onVideoChange} className="hidden" disabled={isUploading || isDirectUploadBusy || isSampleBusy} />
          </label>
          {/* Issue 34: botón para probar con video de muestra */}
          <div className="mt-3">
            <button
              type="button"
              onClick={handleSampleJob}
              disabled={isUploading || isDirectUploadBusy || isSampleBusy}
              className="btn-custom btn-custom-light w-full justify-center disabled:opacity-50"
            >
              {sampleState === 'loading' ? (
                <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" /> Preparando video de muestra...</>
              ) : (
                <><i className="bi bi-play-circle" /> Probar con video de muestra</>
              )}
            </button>
            {sampleState === 'error' && sampleError && (
              <p role="alert" className="text-xs text-red-400 mt-2">{sampleError}</p>
            )}
            <p className="text-xs text-[#94A3B8] mt-2 text-center">
              Usa un clip liviano de ejemplo para evaluar el flujo completo sin subir archivos pesados.
            </p>
          </div>
        </div>

        <div>
          <label className="form-label-custom">
            Archivo de Transcripción <span className="text-[#94A3B8] font-normal">(opcional)</span>
          </label>
          <label className={`dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer ${transcriptFile ? 'has-file' : ''}`}>
            <span className="dropzone-icon-neon mb-3"><i className="bi bi-file-earmark-text" /></span>
            <span className="text-sm font-bold" style={{ color: '#F1F5F9' }}>
              {transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción'}
            </span>
            <span className="text-xs mt-1" style={{ color: '#94A3B8' }}>
              .txt, .srt (UTF-8)
            </span>
            {transcriptFile && (
              <span className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]">
                <i className="bi bi-check-circle-fill" /> {(transcriptFile.size / 1024).toFixed(0)} KB
              </span>
            )}
            <input type="file" accept=".txt,.srt,text/plain" onChange={onTranscriptChange} className="hidden" disabled={isUploading} />
          </label>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0B0F17] p-4 space-y-3">
          <div>
            <p className="text-sm font-bold text-[#F1F5F9]">Subida directa a Cloudflare R2</p>
            <p className="text-xs mt-1 text-[#94A3B8]">Sube el video a R2 y envía su URL prefirmada al worker de RunPod.</p>
          </div>
          <button
            type="button"
            onClick={() => videoFile && void handleFileUpload(videoFile)}
            disabled={!videoFile || directUploadState === 'uploading' || directUploadState === 'processing' || isUploading}
            className="btn-custom btn-custom-light w-full justify-center disabled:opacity-50"
          >
            {directUploadState === 'uploading' || directUploadState === 'processing' ? (
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

        <button type="submit" disabled={isUploading || isDirectUploadBusy || !videoFile} className="btn-custom btn-custom-primary w-full justify-center btn-custom-lg shadow-[0_0_28px_rgba(180,241,5,0.35)]">
          {isUploading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" />
              {status === 'uploading' ? 'Subiendo archivos...' : 'Iniciando procesamiento...'}
            </>
          ) : (
            <>
              <i className="bi bi-lightning-charge-fill" /> Subir y procesar
            </>
          )}
        </button>

        {isUploading && (
          <div className="space-y-2">
            <div className="progress">
              <div className="progress-bar w-full animate-pulse" style={{ height: '10px', borderRadius: '50rem' }} />
            </div>
            <p className="text-xs text-center" style={{ color: '#94A3B8' }}>
              <i className="bi bi-shield-lock mr-1" /> No cierres esta ventana
            </p>
          </div>
        )}
      </form>
    </div>
  )
}
