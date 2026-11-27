import { useState, type ChangeEvent, type FormEvent, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { jobService, videoService } from '@/services/api'
import { ApiError, type RunPodProcessResponse } from '@/types/api'
import Dropzone from '@/components/upload/Dropzone'
import DirectUploadPanel from '@/components/upload/DirectUploadPanel'

type UploadState = 'idle' | 'uploading' | 'creating_job'
type DirectUploadState = 'idle' | 'uploading' | 'processing' | 'success' | 'error'
type SampleState = 'idle' | 'loading' | 'success' | 'error'
type UploadTab = 'file' | 'url'

function fileErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail
  if (err instanceof Error) return err.message
  return 'Error inesperado. Intenta nuevamente.'
}

function resolveJobId(job: { job_id?: string; id: string }): string {
  return job.job_id ?? job.id
}

function persistActiveJobId(jobId: string): void {
  try { localStorage.setItem('clipsai_active_job_id', jobId) } catch {}
}

function renderActiveJobBanner(activeJobId: string | null) {
  if (!activeJobId) return null
  return (
    <div className="rounded-xl border border-[rgba(180,241,5,0.22)] bg-[rgba(180,241,5,0.08)] px-4 py-3 flex items-center justify-between gap-3 mb-6">
      <span className="text-sm font-bold text-[#B4F105] flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#B4F105] animate-pulse" /> Tus clips se están preparando</span>
      <Link to={`/jobs/${activeJobId}`} className="btn-custom btn-custom-primary btn-custom-sm">Ver progreso →</Link>
    </div>
  )
}

function renderErrorAlert(error: string | null) {
  if (!error) return null
  return (
    <div role="alert" className="alert-custom alert-custom-danger">
      <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div className="alert-custom-content">{error}</div>
    </div>
  )
}

function transcriptDropzoneClass(transcriptFile: File | null): string {
  return `dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer ${transcriptFile ? 'has-file' : ''}`
}

function transcriptLabel(transcriptFile: File | null): string {
  return transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción'
}

function transcriptBadge(transcriptFile: File | null) {
  if (!transcriptFile) return null
  return (
    <span className="score-badge-neon high mt-2"><i className="bi bi-check-circle-fill" /> {(transcriptFile.size / 1024).toFixed(0)} KB</span>
  )
}

function submitButtonContent(isUploading: boolean, status: UploadState) {
  if (!isUploading) {
    return (<><i className="bi bi-lightning-charge-fill" /> Crear mis clips</>)
  }
  return (
    <>
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--bg-sidebar)]/30 border-t-[var(--bg-sidebar)]" />
      {status === 'uploading' ? 'Subiendo tu video...' : 'Preparando tus clips...'}
    </>
  )
}

function submitDisabled(isUploading: boolean, isDirectUploadBusy: boolean, hasVideo: boolean): boolean {
  return isUploading || isDirectUploadBusy || !hasVideo
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
  const [activeTab, setActiveTab] = useState<UploadTab>('file')
  const [sourceUrl, setSourceUrl] = useState('')
  const [urlBusy, setUrlBusy] = useState(false)

  useEffect(() => {
    try { const id = localStorage.getItem('clipsai_active_job_id'); if (id) setActiveJobId(id) } catch {}
  }, [])

  const isUploading = status === 'uploading' || status === 'creating_job'
  const isDirectUploadBusy = directUploadState === 'uploading' || directUploadState === 'processing'
  const isSampleBusy = sampleState === 'loading'

  function onVideoChange(e: ChangeEvent<HTMLInputElement>) {
    setVideoFile(e.target.files?.[0] ?? null)
    setDirectUploadState('idle'); setDirectUploadError(null); setDirectUploadKey(null); setDirectUploadResult(null)
  }
  function onTranscriptChange(e: ChangeEvent<HTMLInputElement>) {
    setTranscriptFile(e.target.files?.[0] ?? null)
  }

  async function handleFileUpload(file: File) {
    setDirectUploadState('uploading'); setDirectUploadError(null); setDirectUploadKey(null); setDirectUploadResult(null)
    try {
      const result = await videoService.uploadDirectToStorage(file)
      setDirectUploadKey(result.file_key)
      setDirectUploadState('processing')
      const processResult = await videoService.processDirectUpload(result.file_key)
      setDirectUploadResult(processResult)
      setDirectUploadState('success')
    } catch (err: unknown) {
      setDirectUploadError(fileErrorMessage(err)); setDirectUploadState('error')
    }
  }

  async function handleSampleJob() {
    setSampleState('loading'); setSampleError(null)
    try {
      const job = await videoService.createSampleJob()
      const jobId = resolveJobId(job)
      persistActiveJobId(jobId)
      navigate(`/jobs/${jobId}`, { replace: false })
    } catch (err: unknown) {
      setSampleError(fileErrorMessage(err)); setSampleState('error')
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!videoFile) { setError('Selecciona el archivo de video.'); return }
    setError(null)
    try {
      setStatus('uploading')
      const video = await videoService.upload(videoFile, transcriptFile ?? null)
      setStatus('creating_job')
      const job = await jobService.createJob(video.id)
      const jobId = resolveJobId(job)
      persistActiveJobId(jobId)
      navigate(`/jobs/${jobId}`, { replace: false })
    } catch (err: unknown) {
      setStatus('idle'); setError(fileErrorMessage(err))
    }
  }

  async function handleUrlSubmit(e: FormEvent) {
    e.preventDefault()
    if (!sourceUrl.trim()) { setError('Pega un enlace de YouTube o Twitch.'); return }
    setError(null); setUrlBusy(true)
    try {
      const result = await videoService.createFromUrl(sourceUrl.trim())
      persistActiveJobId(result.job_id)
      navigate(`/jobs/${result.job_id}`, { replace: false })
    } catch (err: unknown) {
      setError(fileErrorMessage(err))
    } finally {
      setUrlBusy(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      {renderActiveJobBanner(activeJobId)}
      <div className="page-header mb-8">
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className="dropzone-icon-neon"><i className="bi bi-cloud-arrow-up" /></span>
            <span className="score-badge-neon high"><i className="bi bi-stars" /> NUEVO</span>
          </div>
          <h1 className="page-title mb-0 text-4xl font-extrabold tracking-tight">Subir video</h1>
          <p className="page-subtitle mt-3 mb-0 max-w-2xl text-sm leading-relaxed">Sube un video y encuentra momentos destacados para convertirlos en clips con IA.</p>
        </div>
      </div>

      {renderErrorAlert(error)}

      <div role="tablist" aria-label="Método de carga" className="mb-4 grid grid-cols-2 gap-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-sidebar)] p-1">
        <button type="button" role="tab" aria-selected={activeTab === 'file'} onClick={() => { setActiveTab('file'); setError(null) }} className={`rounded-lg px-4 py-2.5 text-sm font-bold transition ${activeTab === 'file' ? 'bg-[var(--bg-card)] text-[var(--brand-lime)] shadow-[var(--shadow-sm)]' : 'text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]'}`}><i className="bi bi-upload mr-2" />Subir archivo</button>
        <button type="button" role="tab" aria-selected={activeTab === 'url'} onClick={() => { setActiveTab('url'); setError(null) }} className={`rounded-lg px-4 py-2.5 text-sm font-bold transition ${activeTab === 'url' ? 'bg-[var(--bg-card)] text-[var(--brand-lime)] shadow-[var(--shadow-sm)]' : 'text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]'}`}><i className="bi bi-link-45deg mr-2" />Pegar enlace</button>
      </div>

      <form onSubmit={activeTab === 'url' ? handleUrlSubmit : handleSubmit} className="card-spark space-y-6">
        {activeTab === 'url' ? (
          <div>
            <label htmlFor="video-source-url" className="form-label-custom">Enlace público de YouTube o Twitch</label>
            <input id="video-source-url" type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" className="form-control-custom" autoComplete="url" disabled={urlBusy} />
            <p className="mt-2 text-xs text-[var(--text-secondary)]">El video debe ser público y estar disponible en la región del servidor.</p>
          </div>
        ) : (
          <>
        <div>
          <label className="form-label-custom">Archivo de Video <span className="text-[var(--brand-lime)]">*</span></label>
          <Dropzone videoFile={videoFile} onVideoChange={onVideoChange} sampleState={sampleState} sampleError={sampleError} isUploading={isUploading} isDirectUploadBusy={isDirectUploadBusy} isSampleBusy={isSampleBusy} onSampleJob={handleSampleJob} />
        </div>

        <div>
          <label className="form-label-custom">Archivo de Transcripción <span className="text-[var(--text-secondary)] font-normal">(opcional)</span></label>
          <label className={transcriptDropzoneClass(transcriptFile)}>
            <span className="dropzone-icon-neon mb-3"><i className="bi bi-file-earmark-text" /></span>
            <span className="text-sm font-bold text-[var(--text-primary)]">{transcriptLabel(transcriptFile)}</span>
            <span className="text-xs mt-1 text-[var(--text-secondary)]">.txt, .srt (UTF-8)</span>
            {transcriptBadge(transcriptFile)}
            <input type="file" accept=".txt,.srt,text/plain" onChange={onTranscriptChange} className="hidden" disabled={isUploading} />
          </label>
        </div>

        <DirectUploadPanel videoFile={videoFile} directUploadState={directUploadState} directUploadError={directUploadError} directUploadKey={directUploadKey} directUploadResult={directUploadResult} isUploading={isUploading} onUpload={handleFileUpload} />
          </>
        )}

        <button type="submit" disabled={activeTab === 'url' ? urlBusy || !sourceUrl.trim() : submitDisabled(isUploading, isDirectUploadBusy, !!videoFile)} className="btn-custom btn-custom-primary w-full justify-center btn-custom-lg shadow-[var(--brand-lime-glow)]">
          {activeTab === 'url' ? (urlBusy ? 'Descargando tu video…' : 'Crear mis clips') : submitButtonContent(isUploading, status)}
        </button>

        {activeTab === 'file' && isUploading && (
          <div className="space-y-2">
            <div className="progress"><div className="progress-bar w-full animate-pulse" style={{ height: '10px', borderRadius: '50rem' }} /></div>
            <p className="text-xs text-center text-[var(--text-secondary)]"><i className="bi bi-shield-lock mr-1" /> No cierres esta ventana</p>
          </div>
        )}
      </form>
    </div>
  )
}
