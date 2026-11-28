import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { http } from '@/lib/apiClient'
import { ApiError } from '@/types/api'

type SocialEntry = { connected: boolean; username: string | null; expires_at: string | null }
type SocialStatus = { youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry }

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

interface ConnectSocialIO {
  begin: () => void
  end: () => void
  fail: (msg: string) => void
}

async function connectSocial(path: string, allowedPrefix: string, fallbackError: string, io: ConnectSocialIO): Promise<void> {
  io.begin()
  try {
    const data = await http.get<{ auth_url?: string; url?: string }>(path)
    const resolved = resolveSocialAuthUrl(data, allowedPrefix)
    if ('error' in resolved) { io.fail(resolved.error); return }
    window.location.href = resolved.url
  } catch (e: unknown) {
    io.fail(connectErrorMessage(e, fallbackError))
  } finally { io.end() }
}

export function useIntegrations() {
  const [searchParams, setSearchParams] = useSearchParams()
  const integration = searchParams.get('integration')
  const status = searchParams.get('status')
  const errorDetail = searchParams.get('error') || searchParams.get('message')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [social, setSocial] = useState<SocialStatus | null>(null)

  async function fetchSocialStatus() {
    try {
      const data = await http.get<SocialStatus>('/auth/social/status')
      setSocial(data)
    } catch {}
  }

  useEffect(() => { fetchSocialStatus() }, [])
  useEffect(() => { if (status === 'success') fetchSocialStatus() }, [status])

  useEffect(() => {
    if (status) {
      const t = setTimeout(() => {
        const next = new URLSearchParams(searchParams)
        next.delete('integration'); next.delete('status'); next.delete('error'); next.delete('message')
        setSearchParams(next, { replace: true })
      }, 5000)
      return () => clearTimeout(t)
    }
  }, [status, searchParams, setSearchParams])

  async function handleConnectYoutube() {
    setLoading(true); setError(null)
    try {
      const data = await http.get<{ auth_url: string }>('/auth/social/youtube/connect')
      if (data.auth_url) window.location.href = data.auth_url
      else setError('No se recibió auth_url del backend')
    } catch (e: unknown) {
      setError(connectErrorMessage(e, 'Error al conectar con YouTube'))
    } finally { setLoading(false) }
  }

  async function handleConnectInstagram() {
    await connectSocial('/auth/social/instagram/connect', 'https://www.facebook.com/', 'Error al conectar con Instagram', {
      begin: () => { setLoading(true); setError(null) },
      end: () => setLoading(false),
      fail: setError,
    })
  }

  async function handleConnectTiktok() {
    await connectSocial('/auth/social/tiktok/connect', 'https://www.tiktok.com/', 'Error al conectar con TikTok', {
      begin: () => { setLoading(true); setError(null) },
      end: () => setLoading(false),
      fail: setError,
    })
  }

  async function handleDisconnect(platform: string) {
    setLoading(true); setError(null)
    try {
      await http.delete(`/auth/social/${platform}`)
      await fetchSocialStatus()
    } catch (e: unknown) {
      setError(connectErrorMessage(e, `Error al desconectar ${platform}`))
    } finally { setLoading(false) }
  }

  return {
    integration, status, errorDetail, loading, error, social,
    handleConnectYoutube, handleConnectInstagram, handleConnectTiktok, handleDisconnect,
  }
}
