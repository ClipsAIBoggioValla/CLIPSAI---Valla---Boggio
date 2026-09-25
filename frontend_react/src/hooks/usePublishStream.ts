import { useEffect, useRef, useState } from 'react'
import { TOKEN_KEY } from '@/lib/apiClient'

type PublishStatus = 'PUBLISHING' | 'PUBLISHED' | 'FAILED' | string

export interface UsePublishStreamResult {
  status: PublishStatus | null
  socialPostUrl: string | null
  isPublishing: boolean
  error: string | null
}

const RAW_BASE: string =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()
const API_BASE_URL = (RAW_BASE || 'http://localhost:8000').replace(/\/$/, '')

function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function usePublishStream(clipId: string | null): UsePublishStreamResult {
  const [status, setStatus] = useState<PublishStatus | null>(null)
  const [socialPostUrl, setSocialPostUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!clipId) {
      setStatus(null)
      setSocialPostUrl(null)
      setError(null)
      return
    }

    // Cerrar conexión previa si cambia clipId
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    setError(null)
    setStatus('PUBLISHING')

    // EventSource no permite headers; intentamos pasar token por query param como fallback
    // El backend Express/FastAPI valida Authorization header, pero también puede extender soporte a ?token=
    const token = getToken()
    const url = token
      ? `${API_BASE_URL}/clips/${clipId}/publish-stream?token=${encodeURIComponent(token)}`
      : `${API_BASE_URL}/clips/${clipId}/publish-stream`

    const es = new EventSource(url)
    esRef.current = es

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as {
          status?: string
          publication_status?: string
          social_post_url?: string | null
          socialPostUrl?: string | null
        }
        const nextStatus = (data.publication_status ?? data.status ?? '') as PublishStatus
        if (nextStatus) setStatus(nextStatus.toUpperCase() as PublishStatus)
        const urlVal = (data.social_post_url ?? data.socialPostUrl ?? null) as string | null
        if (urlVal) setSocialPostUrl(urlVal)
        // Detectar terminales
        const term = (nextStatus ?? '').toUpperCase()
        if (term === 'PUBLISHED' || term === 'FAILED') {
          es.close()
          esRef.current = null
        }
      } catch (e) {
        // Si el mensaje no es JSON, ignorar
        console.warn('[usePublishStream] parse error', e)
      }
    }

    const handleDone = () => {
      es.close()
      esRef.current = null
    }

    const handleError = () => {
      // EventSource onerror se dispara en desconexiones; no marcar como fatal si ya está PUBLISHED/FAILED
      // Dejamos que el navegador reintente automáticamente salvo que sea terminal
      setError((prev) => prev ?? null)
    }

    es.addEventListener('message', handleMessage as EventListener)
    es.addEventListener('done', handleDone as EventListener)
    es.addEventListener('error', handleError as EventListener)
    // Algunos backends envían 'done' como evento genérico con data {}
    es.onerror = handleError

    return () => {
      es.removeEventListener('message', handleMessage as EventListener)
      es.removeEventListener('done', handleDone as EventListener)
      es.removeEventListener('error', handleError as EventListener)
      es.close()
      if (esRef.current === es) esRef.current = null
    }
  }, [clipId])

  const isPublishing = status === 'PUBLISHING'

  return { status, socialPostUrl, isPublishing, error }
}
