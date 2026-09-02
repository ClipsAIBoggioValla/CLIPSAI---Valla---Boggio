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
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Subir video</h1>
          <p className="text-slate-600 mt-2">Sube tu video y su transcripción para generar clips automáticamente.</p>
        </div>

        {error && (
          <div role="alert" className="mb-6 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 flex gap-3">
            <span className="text-red-400">⚠</span>
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl p-6 sm:p-8 space-y-6">
          <div>
            <label className="block text-slate-900 dark:text-white font-bold mb-2">
              Archivo de Video <span className="text-brand-500">*</span>
            </label>
            <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 bg-slate-50 dark:bg-slate-800/50 border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 transition p-6 sm:p-8 cursor-pointer">
              <span className="text-3xl mb-2">🎬</span>
              <span className="text-slate-800 dark:text-slate-200 font-semibold">
                {videoFile ? videoFile.name : 'Arrastra o selecciona tu video'}
              </span>
              <span className="text-slate-600 dark:text-slate-400 font-medium mt-1">.mp4, .mov (máx. 500MB)</span>
              {videoFile && (
                <span className="text-xs text-brand-500 mt-2">{(videoFile.size / 1024 / 1024).toFixed(1)} MB</span>
              )}
              <input
                type="file"
                accept=".mp4,.mov,.avi,video/mp4,video/quicktime"
                onChange={onVideoChange}
                className="hidden"
                disabled={isUploading}
              />
            </label>
          </div>

          <div>
            <label className="block text-slate-900 dark:text-white font-bold mb-2">
              Archivo de Transcripción <span className="text-brand-500">*</span>
            </label>
            <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 bg-slate-50 dark:bg-slate-800/50 border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-violet-500 transition p-6 sm:p-8 cursor-pointer">
              <span className="text-3xl mb-2">📄</span>
              <span className="text-slate-800 dark:text-slate-200 font-semibold">
                {transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción'}
              </span>
              <span className="text-slate-600 dark:text-slate-400 font-medium mt-1">.txt (UTF-8)</span>
              {transcriptFile && (
                <span className="text-xs text-brand-500 mt-2">{(transcriptFile.size / 1024).toFixed(0)} KB</span>
              )}
              <input
                type="file"
                accept=".txt,.srt,text/plain"
                onChange={onTranscriptChange}
                className="hidden"
                disabled={isUploading}
              />
            </label>
          </div>

          <button
            type="submit"
            disabled={isUploading || !videoFile || !transcriptFile}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold py-3.5 px-4 transition"
          >
            {isUploading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                {status === 'uploading' ? 'Subiendo archivos...' : 'Iniciando procesamiento...'}
              </>
            ) : (
              'Subir y procesar'
            )}
          </button>

          {isUploading && (
            <div className="space-y-2">
              <div className="h-2 bg-white dark:bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full w-full bg-gradient-to-r from-violet-600 to-indigo-600 animate-pulse rounded-full" />
              </div>
              <p className="text-xs text-center text-slate-600">No cierres esta ventana</p>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
