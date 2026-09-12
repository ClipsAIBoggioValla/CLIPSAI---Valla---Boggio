import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { http } from '@/lib/apiClient'
import { ApiError } from '@/types/api'

type SocialEntry = { connected: boolean; username: string | null; expires_at: string | null }
type SocialStatus = { youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry }

export default function IntegrationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const integration = searchParams.get('integration')
  const status = searchParams.get('status')
  const errorDetail = searchParams.get('error') || searchParams.get('message')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [social, setSocial] = useState<SocialStatus | null>(null)

  async function fetchSocialStatus() {
    try {
      const token = (() => {
        try {
          return localStorage.getItem('clipsai_token')
        } catch {
          return null
        }
      })()
      const data = await http.get<SocialStatus>('/auth/social/status', token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
      console.log("[DEBUG] Respuesta /auth/social/status:", data)
      setSocial(data)
    } catch {}
  }

  useEffect(() => {
    fetchSocialStatus()
  }, [])

  useEffect(() => {
    if (status === 'success') fetchSocialStatus()
  }, [status])

  useEffect(() => {
    if (status) {
      const t = setTimeout(() => {
        const next = new URLSearchParams(searchParams)
        next.delete('integration')
        next.delete('status')
        next.delete('error')
        next.delete('message')
        setSearchParams(next, { replace: true })
      }, 5000)
      return () => clearTimeout(t)
    }
  }, [status, searchParams, setSearchParams])

  async function handleConnectYoutube() {
    setLoading(true)
    setError(null)
    try {
      const data = await http.get<{ auth_url: string }>('/auth/social/youtube/connect')
      if (data.auth_url) {
        window.location.href = data.auth_url
      } else {
        setError('No se recibió auth_url del backend')
      }
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.detail)
      else if (e instanceof Error) setError(e.message)
      else setError('Error al conectar con YouTube')
    } finally {
      setLoading(false)
    }
  }

  async function handleConnectInstagram() {
    setLoading(true)
    setError(null)
    try {
      const token = (() => {
        try {
          return localStorage.getItem('clipsai_token')
        } catch {
          return null
        }
      })()
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
      const data = await http.get<{ auth_url?: string; url?: string }>('/auth/social/instagram/connect', headers ? { headers } : undefined)
      const authUrl = (data as { auth_url?: string; url?: string }).auth_url || (data as { auth_url?: string; url?: string }).url
      console.log("[DEBUG] Auth URL recibida del backend:", authUrl)
      if (!authUrl) {
        setError('No se recibió auth_url del backend')
        return
      }
      if (!authUrl.startsWith("https://www.facebook.com/")) {
        setError('URL de autorización inválida: debe comenzar con https://www.facebook.com/')
        return
      }
      window.location.href = authUrl
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.detail)
      else if (e instanceof Error) setError(e.message)
      else setError('Error al conectar con Instagram')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="page-header" style={{ marginBottom: '2rem' }}>
        <div className="flex items-center gap-4">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#FF0000] text-white border border-[rgba(255,0,0,0.3)] shadow-[0_0_16px_rgba(255,0,0,0.35)]">
            <i className="bi bi-youtube" style={{ fontSize: '1.5rem' }} />
          </span>
          <div>
            <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.35rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>
              Integraciones
            </h1>
            <p className="page-subtitle" style={{ marginBottom: 0, fontSize: '0.98rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6 }}>
              Conecta tus redes sociales para publicación automática
            </p>
          </div>
        </div>
      </div>

      {integration === 'youtube' && status === 'success' && (
        <div role="alert" className="alert-custom alert-custom-success mb-4">
          <i className="bi bi-check-circle-fill alert-custom-icon" />
          <div className="alert-custom-content">
            <strong>YouTube conectado correctamente</strong> — integración <code>youtube</code> vinculada a tu cuenta. Ya puedes publicar clips en YouTube.
          </div>
        </div>
      )}
      {integration === 'youtube' && status === 'error' && (
        <div role="alert" className="alert-custom alert-custom-danger mb-4">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content">
            <strong>Error al conectar YouTube</strong> {errorDetail ? `— ${errorDetail}` : ''}. Intenta nuevamente.
          </div>
        </div>
      )}
      {integration === 'instagram' && status === 'success' && (
        <div role="alert" className="alert-custom alert-custom-success mb-4">
          <i className="bi bi-check-circle-fill alert-custom-icon" />
          <div className="alert-custom-content">
            <strong>Instagram conectado correctamente</strong> — integración <code>instagram</code> vinculada a tu cuenta. Ya puedes publicar Reels en Instagram.
          </div>
        </div>
      )}
      {integration === 'instagram' && status === 'error' && (
        <div role="alert" className="alert-custom alert-custom-danger mb-4">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content">
            <strong>Error al conectar Instagram</strong> {errorDetail ? `— ${errorDetail}` : ''}. Intenta nuevamente.
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="alert-custom alert-custom-danger mb-4">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content">{error}</div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card-spark">
          <div className="flex items-center gap-3 mb-3">
            <span className="h-10 w-10 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000] text-xl">
              <i className="bi bi-youtube" />
            </span>
            <div>
              <h3 className="font-bold text-white">YouTube</h3>
              {social?.youtube.connected && social.youtube.username ? (
                <p className="text-xs font-mono text-emerald-300">@{social.youtube.username}</p>
              ) : (
                <p className="text-xs text-[#94A3B8]">Google Data API v3 — upload + readonly</p>
              )}
            </div>
            {social?.youtube.connected ? (
              <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado
              </span>
            ) : integration === 'youtube' && status === 'success' ? (
              <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado
              </span>
            ) : (
              <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-white/5 text-[#94A3B8] border border-white/10">
                No conectado
              </span>
            )}
          </div>
          <p className="text-sm text-[#94A3B8] mb-4">
            Conecta tu canal para subir clips directamente como Shorts. Scopes: <code className="text-xs bg-white/5 px-1 py-0.5 rounded">youtube.readonly</code> + <code className="text-xs bg-white/5 px-1 py-0.5 rounded">youtube.upload</code>
          </p>
          <button
            onClick={handleConnectYoutube}
            disabled={loading}
            className="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2"
            data-testid="connect-youtube-btn"
          >
            {loading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" /> Conectando...
              </>
            ) : (
              <>
                <i className="bi bi-box-arrow-up-right" /> Conectar YouTube
              </>
            )}
          </button>
          <p className="text-xs text-[#64748B] mt-2 text-center">
            GET <code>/auth/social/youtube/connect</code> → redirect Google OAuth (offline + consent)
          </p>
        </div>

        <div className="card-spark">
          <div className="flex items-center gap-3 mb-3">
            <span className="h-10 w-10 rounded-xl bg-[#E1306C]/10 border border-[#E1306C]/20 flex items-center justify-center text-[#E1306C] text-xl">
              <i className="bi bi-instagram" />
            </span>
            <div>
              <h3 className="font-bold text-white">Instagram</h3>
              {social?.instagram.connected && social.instagram.username ? (
                <p className="text-xs font-mono text-emerald-300">@{social.instagram.username}</p>
              ) : (
                <p className="text-xs text-[#94A3B8]">Meta Graph API — instagram_basic + content_publish</p>
              )}
            </div>
            {social?.instagram.connected ? (
              <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado
              </span>
            ) : integration === 'instagram' && status === 'success' ? (
              <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado
              </span>
            ) : (
              <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-white/5 text-[#94A3B8] border border-white/10">
                No conectado
              </span>
            )}
          </div>
          <p className="text-sm text-[#94A3B8] mb-4">
            Conecta tu cuenta para publicar Reels automáticamente. Scopes: <code className="text-xs bg-white/5 px-1 py-0.5 rounded">instagram_basic</code> + <code className="text-xs bg-white/5 px-1 py-0.5 rounded">instagram_content_publish</code> + <code className="text-xs bg-white/5 px-1 py-0.5 rounded">pages_show_list</code>
          </p>
          <button
            onClick={handleConnectInstagram}
            disabled={loading}
            className="btn-custom w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#F58529] via-[#DD2A7B] to-[#515BD4] text-white border-0 hover:opacity-90"
            data-testid="connect-instagram-btn"
          >
            {loading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Conectando...
              </>
            ) : (
              <>
                <i className="bi bi-instagram" /> Conectar Instagram
              </>
            )}
          </button>
          <p className="text-xs text-[#64748B] mt-2 text-center">
            GET <code>/auth/social/instagram/connect</code> → redirect Meta OAuth (long-lived 60 días)
          </p>
        </div>
      </div>

      <div className="card-spark mt-4 bg-[#0B0F17]/50">
        <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
          <i className="bi bi-info-circle text-[#B4F105]" /> Cómo probar el flujo completo
        </h4>
        <ol className="list-decimal list-inside text-sm text-[#94A3B8] space-y-1">
          <li>
            Asegúrate de tener <code>GOOGLE_CLIENT_ID</code> / <code>GOOGLE_CLIENT_SECRET</code> en <code>.env</code> y backend en{' '}
            <code>https://decorator-excretory-satin.ngrok-free.dev</code> o <code>http://localhost:8000</code>
          </li>
          <li>
            Haz clic en <strong>Conectar YouTube</strong> arriba (llama a <code>GET /auth/social/youtube/connect</code> con tu JWT)
          </li>
          <li>Serás redirigido a <code>accounts.google.com</code> — acepta scopes <code>youtube.readonly</code> + <code>youtube.upload</code></li>
          <li>
            Google redirige a <code>/auth/social/youtube/callback?code=...&state=...</code> → backend intercambia tokens → guarda en <code>social_accounts</code> → redirige aquí a{' '}
            <code>?integration=youtube&status=success</code>
          </li>
          <li>Verifica en DB: <code>SELECT platform, platform_account_id FROM social_accounts WHERE platform='youtube'</code></li>
        </ol>
      </div>
    </div>
  )
}
