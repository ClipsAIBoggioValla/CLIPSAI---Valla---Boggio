import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { http } from '@/lib/apiClient'
import { ApiError } from '@/types/api'

type SocialEntry = { connected: boolean; username: string | null; expires_at: string | null }
type SocialStatus = { youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry }

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
      const token = (() => { try { return localStorage.getItem('clipsai_token') } catch { return null } })()
      const data = await http.get<SocialStatus>('/auth/social/status', token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
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
      if (e instanceof ApiError) setError(e.detail)
      else if (e instanceof Error) setError(e.message)
      else setError('Error al conectar con YouTube')
    } finally { setLoading(false) }
  }

  async function handleConnectInstagram() {
    setLoading(true); setError(null)
    try {
      const token = (() => { try { return localStorage.getItem('clipsai_token') } catch { return null } })()
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
      const data = await http.get<{ auth_url?: string; url?: string }>('/auth/social/instagram/connect', headers ? { headers } : undefined)
      const authUrl = (data as { auth_url?: string; url?: string }).auth_url || (data as { auth_url?: string; url?: string }).url
      if (!authUrl) { setError('No se recibió auth_url del backend'); return }
      if (!authUrl.startsWith('https://www.facebook.com/')) { setError('URL de autorización inválida: debe comenzar con https://www.facebook.com/'); return }
      window.location.href = authUrl
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.detail)
      else if (e instanceof Error) setError(e.message)
      else setError('Error al conectar con Instagram')
    } finally { setLoading(false) }
  }

  async function handleConnectTiktok() {
    setLoading(true); setError(null)
    try {
      const token = (() => { try { return localStorage.getItem('clipsai_token') } catch { return null } })()
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
      const data = await http.get<{ auth_url?: string; url?: string }>('/auth/social/tiktok/connect', headers ? { headers } : undefined)
      const authUrl = (data as { auth_url?: string; url?: string }).auth_url || (data as { auth_url?: string; url?: string }).url
      if (!authUrl) { setError('No se recibió auth_url del backend'); return }
      if (!authUrl.startsWith('https://www.tiktok.com/')) { setError('URL de autorización inválida: debe comenzar con https://www.tiktok.com/'); return }
      window.location.href = authUrl
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.detail)
      else if (e instanceof Error) setError(e.message)
      else setError('Error al conectar con TikTok')
    } finally { setLoading(false) }
  }

  async function handleDisconnect(platform: string) {
    setLoading(true); setError(null)
    try {
      await http.delete(`/auth/social/${platform}`)
      await fetchSocialStatus()
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.detail)
      else if (e instanceof Error) setError(e.message)
      else setError(`Error al desconectar ${platform}`)
    } finally { setLoading(false) }
  }

  return {
    integration, status, errorDetail, loading, error, social,
    handleConnectYoutube, handleConnectInstagram, handleConnectTiktok, handleDisconnect,
  }
}
