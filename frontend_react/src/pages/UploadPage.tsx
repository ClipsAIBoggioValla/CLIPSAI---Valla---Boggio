import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobService, videoService } from '@/services/api'
import { ApiError } from '@/types/api'

type UploadState = 'idle' | 'uploading' | 'creating_job'

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

  const isUploading = status === 'uploading' || status === 'creating_job'

  function onVideoChange(e: ChangeEvent<HTMLInputElement>) {
    setVideoFile(e.target.files?.[0] ?? null)
  }
  function onTranscriptChange(e: ChangeEvent<HTMLInputElement>) {
    setTranscriptFile(e.target.files?.[0] ?? null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!videoFile || !transcriptFile) {
      setError('Selecciona ambos archivos: video y transcripción.')
      return
    }
    setError(null)
    try {
      setStatus('uploading')
      const video = await videoService.upload(videoFile, transcriptFile)
      setStatus('creating_job')
      const job = await jobService.createJob(video.id)
      const jobId = job.job_id ?? job.id
      navigate(`/jobs/${jobId}`, { replace: false })
    } catch (err: unknown) {
      setStatus('idle')
      setError(fileErrorMessage(err))
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
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
            <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" onChange={onVideoChange} className="hidden" disabled={isUploading} />
          </label>
        </div>

        <div>
          <label className="form-label-custom">
            Archivo de Transcripción <span className="text-[#B4F105]">*</span>
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

        <button type="submit" disabled={isUploading || !videoFile || !transcriptFile} className="btn-custom btn-custom-primary w-full justify-center btn-custom-lg shadow-[0_0_28px_rgba(180,241,5,0.35)]">
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
