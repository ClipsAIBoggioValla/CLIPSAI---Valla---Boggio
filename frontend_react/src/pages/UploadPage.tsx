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
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Subir video</h1>
          <p className="text-gray-400 mt-2">Sube tu video y su transcripción para generar clips automáticamente.</p>
        </div>

        {error && (
          <div role="alert" className="mb-6 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 flex gap-3">
            <span className="text-red-400">⚠</span>
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-2xl p-6 sm:p-8 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Archivo de Video <span className="text-violet-400">*</span>
            </label>
            <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-700 bg-gray-800/50 hover:bg-gray-800 hover:border-gray-600 transition p-6 sm:p-8 cursor-pointer">
              <span className="text-3xl mb-2">🎬</span>
              <span className="text-sm font-medium text-gray-200">
                {videoFile ? videoFile.name : 'Arrastra o selecciona tu video'}
              </span>
              <span className="text-xs text-gray-500 mt-1">.mp4, .mov (máx. 500MB)</span>
              {videoFile && (
                <span className="text-xs text-violet-400 mt-2">{(videoFile.size / 1024 / 1024).toFixed(1)} MB</span>
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
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Archivo de Transcripción <span className="text-violet-400">*</span>
            </label>
            <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-700 bg-gray-800/50 hover:bg-gray-800 hover:border-gray-600 transition p-6 sm:p-8 cursor-pointer">
              <span className="text-3xl mb-2">📄</span>
              <span className="text-sm font-medium text-gray-200">
                {transcriptFile ? transcriptFile.name : 'Arrastra o selecciona tu transcripción'}
              </span>
              <span className="text-xs text-gray-500 mt-1">.txt (UTF-8)</span>
              {transcriptFile && (
                <span className="text-xs text-violet-400 mt-2">{(transcriptFile.size / 1024).toFixed(0)} KB</span>
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
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-medium py-3.5 px-4 transition"
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
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full w-full bg-violet-600 animate-pulse rounded-full" />
              </div>
              <p className="text-xs text-center text-gray-500">No cierres esta ventana</p>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
