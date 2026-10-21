import { useIntegrations } from '@/hooks/useIntegrations'
import PlatformCard from '@/components/integrations/PlatformCard'

export default function IntegrationsPage() {
  const {
    integration, status, errorDetail, loading, error, social,
    handleConnectYoutube, handleConnectInstagram,
  } = useIntegrations()

  const youtubeConnected = social?.youtube.connected || (integration === 'youtube' && status === 'success')
  const instagramConnected = social?.instagram.connected || (integration === 'instagram' && status === 'success')

  return (
    <div className="max-w-4xl mx-auto">
      <div className="page-header" style={{ marginBottom: '2rem' }}>
        <div className="flex items-center gap-4">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#FF0000] text-white border border-[rgba(255,0,0,0.3)] shadow-[0_0_16px_rgba(255,0,0,0.35)]">
            <i className="bi bi-youtube" style={{ fontSize: '1.5rem' }} />
          </span>
          <div>
            <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.35rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>Integraciones</h1>
            <p className="page-subtitle" style={{ marginBottom: 0, fontSize: '0.98rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6 }}>Conecta tus redes sociales para publicación automática</p>
          </div>
        </div>
      </div>

      {integration === 'youtube' && status === 'success' && (
        <div role="alert" className="alert-custom alert-custom-success mb-4">
          <i className="bi bi-check-circle-fill alert-custom-icon" />
          <div className="alert-custom-content"><strong>YouTube conectado correctamente</strong> — integración <code>youtube</code> vinculada a tu cuenta. Ya puedes publicar clips en YouTube.</div>
        </div>
      )}
      {integration === 'youtube' && status === 'error' && (
        <div role="alert" className="alert-custom alert-custom-danger mb-4">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content"><strong>Error al conectar YouTube</strong> {errorDetail ? `— ${errorDetail}` : ''}. Intenta nuevamente.</div>
        </div>
      )}
      {integration === 'instagram' && status === 'success' && (
        <div role="alert" className="alert-custom alert-custom-success mb-4">
          <i className="bi bi-check-circle-fill alert-custom-icon" />
          <div className="alert-custom-content"><strong>Instagram conectado correctamente</strong> — integración <code>instagram</code> vinculada a tu cuenta. Ya puedes publicar Reels en Instagram.</div>
        </div>
      )}
      {integration === 'instagram' && status === 'error' && (
        <div role="alert" className="alert-custom alert-custom-danger mb-4">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content"><strong>Error al conectar Instagram</strong> {errorDetail ? `— ${errorDetail}` : ''}. Intenta nuevamente.</div>
        </div>
      )}
      {error && (
        <div role="alert" className="alert-custom alert-custom-danger mb-4">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content">{error}</div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PlatformCard
          name="YouTube"
          icon="bi bi-youtube"
          iconWrapClass="h-10 w-10 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000] text-xl"
          connected={!!youtubeConnected}
          username={social?.youtube.username ?? null}
          description="Google Data API v3 — upload + readonly"
          descriptionLong="Conecta tu canal para subir clips directamente como Shorts. Scopes: youtube.readonly + youtube.upload"
          endpointHint="GET /auth/social/youtube/connect → redirect Google OAuth (offline + consent)"
          loading={loading}
          onConnect={handleConnectYoutube}
          connectLabel="Conectar YouTube"
          connectIcon="bi bi-box-arrow-up-right"
          connectClass="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2"
        />

        <PlatformCard
          name="Instagram"
          icon="bi bi-instagram"
          iconWrapClass="h-10 w-10 rounded-xl bg-[#E1306C]/10 border border-[#E1306C]/20 flex items-center justify-center text-[#E1306C] text-xl"
          connected={!!instagramConnected}
          username={social?.instagram.username ?? null}
          description="Meta Graph API — instagram_basic + content_publish"
          descriptionLong="Conecta tu cuenta para publicar Reels automáticamente. Scopes: instagram_basic + instagram_content_publish + pages_show_list"
          endpointHint="GET /auth/social/instagram/connect → redirect Meta OAuth (long-lived 60 días)"
          loading={loading}
          onConnect={handleConnectInstagram}
          connectLabel="Conectar Instagram"
          connectIcon="bi bi-instagram"
          connectClass="btn-custom w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#F58529] via-[#DD2A7B] to-[#515BD4] text-white border-0 hover:opacity-90"
        />
      </div>

      <div className="card-spark mt-4 bg-[#0B0F17]/50">
        <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2"><i className="bi bi-info-circle text-[#B4F105]" /> Cómo probar el flujo completo</h4>
        <ol className="list-decimal list-inside text-sm text-[#94A3B8] space-y-1">
          <li>Asegúrate de tener <code>GOOGLE_CLIENT_ID</code> / <code>GOOGLE_CLIENT_SECRET</code> en <code>.env</code> y backend en <code>https://decorator-excretory-satin.ngrok-free.dev</code> o <code>http://localhost:8000</code></li>
          <li>Haz clic en <strong>Conectar YouTube</strong> arriba (llama a <code>GET /auth/social/youtube/connect</code> con tu JWT)</li>
          <li>Serás redirigido a <code>accounts.google.com</code> — acepta scopes <code>youtube.readonly</code> + <code>youtube.upload</code></li>
          <li>Google redirige a <code>/auth/social/youtube/callback?code=...&amp;state=...</code> → backend intercambia tokens → guarda en <code>social_accounts</code> → redirige aquí a <code>?integration=youtube&amp;status=success</code></li>
          <li>Verifica en DB: <code>SELECT platform, platform_account_id FROM social_accounts WHERE platform='youtube'</code></li>
        </ol>
      </div>
    </div>
  )
}
