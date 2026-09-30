import { useEffect, useRef, useState } from 'react'
import { TOKEN_KEY } from '@/lib/apiClient'

export type PublishSSEStatus = 'PUBLISHING' | 'PUBLISHED' | 'FAILED' | string

export interface PublishSSEPayload {
  clip_id: string
  status: PublishSSEStatus
  social_post_url: string | null
  error_log: string | null
}

export interface UsePublishSSEResult {
  status: PublishSSEStatus | null
  socialPostUrl: string | null
  errorLog: string | null
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

export function usePublishSSE(clipId: string | null): UsePublishSSEResult {
  const [status, setStatus] = useState<PublishSSEStatus | null>(null)
  const [socialPostUrl, setSocialPostUrl] = useState<string | null>(null)
  const [errorLog, setErrorLog] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!clipId) {
      setStatus(null)
      setSocialPostUrl(null)
      setErrorLog(null)
      setError(null)
      return
    }

    const token = getToken()
    if (!token) {
      setStatus(null)
      setError('No se encontró un token de sesión válido')
      return
    }

    setStatus('PUBLISHING')
    setSocialPostUrl(null)
    setErrorLog(null)
    setError(null)

    const url = new URL(`${API_BASE_URL}/clips/${encodeURIComponent(clipId)}/publish-stream`)
    url.searchParams.set('token', token)
    const eventSource = new EventSource(url.toString())
    eventSourceRef.current = eventSource

    const closeConnection = () => {
      eventSource.close()
      if (eventSourceRef.current === eventSource) eventSourceRef.current = null
    }

    const handleMessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as Partial<PublishSSEPayload>
        if (typeof payload.status === 'string') {
          const nextStatus = payload.status.toUpperCase()
          setStatus(nextStatus)
          if (nextStatus === 'PUBLISHED' || nextStatus === 'FAILED') closeConnection()
        }
        if (typeof payload.social_post_url === 'string') setSocialPostUrl(payload.social_post_url)
        if (typeof payload.error_log === 'string') setErrorLog(payload.error_log)
      } catch (cause: unknown) {
        setError(cause instanceof Error ? `Respuesta SSE inválida: ${cause.message}` : 'Respuesta SSE inválida')
      }
    }

    const handleDone = () => closeConnection()
    const handleStreamError = (event: Event) => {
      const messageEvent = event as MessageEvent<string>
      if (typeof messageEvent.data !== 'string' || !messageEvent.data) return
      try {
        const payload = JSON.parse(messageEvent.data) as { detail?: unknown }
        if (typeof payload.detail === 'string') setError(payload.detail)
      } catch (cause: unknown) {
        setError(cause instanceof Error ? cause.message : 'Error en el flujo SSE')
      }
    }

    eventSource.addEventListener('message', handleMessage as EventListener)
    eventSource.addEventListener('done', handleDone)
    eventSource.addEventListener('error', handleStreamError)

    return () => {
      eventSource.removeEventListener('message', handleMessage as EventListener)
      eventSource.removeEventListener('done', handleDone)
      eventSource.removeEventListener('error', handleStreamError)
      closeConnection()
    }
  }, [clipId])

  return {
    status,
    socialPostUrl,
    errorLog,
    isPublishing: status === 'PUBLISHING',
    error,
  }
}
