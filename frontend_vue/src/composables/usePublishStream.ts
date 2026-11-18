import { ref, watch, onUnmounted, isRef, unref } from 'vue'
import type { Ref } from 'vue'
import { TOKEN_KEY } from '@/api/client'

type PublishStatus = 'PUBLISHING' | 'PUBLISHED' | 'FAILED' | string

export interface UsePublishStreamResult {
  status: ReturnType<typeof ref<PublishStatus | null>>
  socialPostUrl: ReturnType<typeof ref<string | null>>
  isPublishing: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string | null>>
}

const RAW = (import.meta.env.VITE_API_URL as string | undefined ?? '').trim()
const API_BASE_URL = (RAW || 'http://localhost:8000').replace(/\/$/, '')

function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

type ParsedPublishPayload = {
  status?: string
  publication_status?: string
  social_post_url?: string | null
}

function isTerminalPublishStatus(status: string): boolean {
  return status === 'PUBLISHED' || status === 'FAILED'
}

function nextStatusFrom(data: ParsedPublishPayload): PublishStatus {
  return (data.publication_status ?? data.status ?? '') as PublishStatus
}

interface PublishStateRefs {
  status: Ref<PublishStatus | null>
  socialPostUrl: Ref<string | null>
  isPublishing: Ref<boolean>
  close: () => void
}

function applyPublishStatus(next: PublishStatus, refs: PublishStateRefs): void {
  if (!next) return
  refs.status.value = next.toUpperCase() as PublishStatus
  refs.isPublishing.value = next.toUpperCase() === 'PUBLISHING'
}

function applyPublishPayload(data: ParsedPublishPayload, refs: PublishStateRefs): void {
  const next = nextStatusFrom(data)
  applyPublishStatus(next, refs)
  const urlVal = (data.social_post_url as string | null) ?? null
  if (urlVal) refs.socialPostUrl.value = urlVal
  if (isTerminalPublishStatus(next)) {
    refs.close()
    refs.isPublishing.value = false
  }
}

export function usePublishStream(clipId: string | null | Ref<string | null> | (() => string | null)) {
  const status = ref<PublishStatus | null>(null)
  const socialPostUrl = ref<string | null>(null)
  const isPublishing = ref(false)
  const error = ref<string | null>(null)
  let es: EventSource | null = null

  function close() {
    if (es) {
      es.close()
      es = null
    }
  }

  function connect(id: string) {
    close()
    error.value = null
    status.value = 'PUBLISHING'
    isPublishing.value = true

    const token = getToken()
    const url = token
      ? `${API_BASE_URL}/clips/${id}/publish-stream?token=${encodeURIComponent(token)}`
      : `${API_BASE_URL}/clips/${id}/publish-stream`

    es = new EventSource(url)

    const handleMessage = (event: MessageEvent) => {
      try {
        applyPublishPayload(JSON.parse(event.data) as ParsedPublishPayload, { status, socialPostUrl, isPublishing, close })
      } catch (e) {
        console.warn('[usePublishStream] parse error', e)
      }
    }

    const handleDone = () => {
      close()
      isPublishing.value = false
    }

    const handleError = () => {
      // No marcar error fatal, EventSource reintentará
    }

    es.addEventListener('message', handleMessage as EventListener)
    es.addEventListener('done', handleDone as EventListener)
    es.addEventListener('error', handleError as EventListener)
    es.onerror = handleError
  }

  const resolve = () => {
    if (isRef(clipId)) return (clipId as Ref<string | null>).value
    if (typeof clipId === 'function') return (clipId as () => string | null)()
    return clipId as string | null
  }
  watch(
    resolve,
    (id) => {
      if (!id) {
        close()
        status.value = null
        socialPostUrl.value = null
        isPublishing.value = false
        error.value = null
        return
      }
      connect(id)
    },
    { immediate: true }
  )

  onUnmounted(() => close())

  return { status, socialPostUrl, isPublishing, error, close }
}
