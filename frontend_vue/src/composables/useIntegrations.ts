import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '@/api/client'
import { ApiError } from '@/types/api'
import PlatformCard from '@/components/integrations/PlatformCard.vue'

function readStoredToken(): string | null {
  try {
    return localStorage.getItem('clipsai_token')
  } catch {
    return null
  }
}

function socialHeaders(): Record<string, string> {
  const token = readStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function connectErrorMessage(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.detail : e instanceof Error ? e.message : fallback
}

type SocialUrlResolution = { url: string } | { error: string }

function resolveSocialAuthUrl(
  data: { auth_url?: string; url?: string },
  allowedPrefix: string,
): SocialUrlResolution {
  const authUrl = data.auth_url || data.url
  if (!authUrl) return { error: 'No se recibió auth_url del backend' }
  if (!authUrl.startsWith(allowedPrefix)) {
    return { error: `URL de autorización inválida: debe comenzar con ${allowedPrefix}` }
  }
  return { url: authUrl }
}

export function useIntegrations() {

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const error = ref<string | null>(null)

const integration = ref<string | null>(null)
const status = ref<string | null>(null)
const errorDetail = ref<string | null>(null)

type SocialEntry = { connected: boolean; username: string | null; expires_at: string | null }
const social = ref<{ youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry } | null>(null)

async function fetchSocialStatus() {
  try {
    const headers = socialHeaders()
    const { data } = await apiClient.get<{ youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry }>('/auth/social/status', { headers })
    social.value = data
  } catch {}
}

function syncQuery() {
  integration.value = route.query.integration as string | null
  status.value = route.query.status as string | null
  errorDetail.value = (route.query.error as string | null) || (route.query.message as string | null)
}

onMounted(async () => {
  syncQuery()
  await fetchSocialStatus()
  if (status.value === 'success') await fetchSocialStatus()
  if (status.value) {
    setTimeout(() => {
      const q = { ...route.query }
      delete q.integration
      delete q.status
      delete q.error
      delete (q as Record<string, unknown>).message
      router.replace({ query: q })
      syncQuery()
    }, 5000)
  }
})

async function handleConnectYoutube() {
  loading.value = true
  error.value = null
  try {
    const { data } = await apiClient.get<{ auth_url: string }>('/auth/social/youtube/connect')
    if (data.auth_url) window.location.href = data.auth_url
    else error.value = 'No se recibió auth_url del backend'
  } catch (e: unknown) {
    if (e instanceof ApiError) error.value = e.detail
    else if (e instanceof Error) error.value = e.message
    else error.value = 'Error al conectar con YouTube'
  } finally {
    loading.value = false
  }
}

async function handleConnectInstagram() {
  loading.value = true
  error.value = null
  try {
    const headers = socialHeaders()
    const { data } = await apiClient.get<{ auth_url?: string; url?: string }>('/auth/social/instagram/connect', { headers })
    const resolved = resolveSocialAuthUrl(data, 'https://www.facebook.com/')
    if ('error' in resolved) {
      error.value = resolved.error
      return
    }
    window.location.href = resolved.url
  } catch (e: unknown) {
    error.value = connectErrorMessage(e, 'Error al conectar con Instagram')
  } finally {
    loading.value = false
  }
}
return {
  error,
  errorDetail,
  fetchSocialStatus,
  handleConnectInstagram,
  handleConnectYoutube,
  integration,
  loading,
  route,
  router,
  social,
  status,
  syncQuery,
}
}
