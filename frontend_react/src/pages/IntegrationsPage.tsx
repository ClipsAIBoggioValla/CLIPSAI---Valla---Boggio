import { useIntegrations } from '@/hooks/useIntegrations'
import PlatformCard from '@/components/integrations/PlatformCard'

type SocialEntryLike = { connected: boolean; username: string | null }
type SocialStatusLike = { youtube: SocialEntryLike; instagram: SocialEntryLike; tiktok: SocialEntryLike }
type IntegrationPlatform = 'youtube' | 'instagram' | 'tiktok'

const DISPLAY_NAMES: Record<IntegrationPlatform, string> = {
  youtube: 'YouTube',
  instagram: 'Instagram',
  tiktok: 'TikTok',
}

function platformConnected(
  social: SocialStatusLike | null,
  integration: string | null,
  status: string | null,
  platform: IntegrationPlatform,
): boolean | undefined {
  return social?.[platform].connected || (integration === platform && status === 'success')
}

function platformUsername(social: SocialStatusLike | null, platform: IntegrationPlatform): string | null {
  return social?.[platform].username ?? null
}

function renderConnectedAlert(displayName: string, code: string, publishText: string) {
  return (
    <div role="alert" className="alert-custom alert-custom-success mb-4">
      <i className="bi bi-check-circle-fill alert-custom-icon" />
      <div className="alert-custom-content"><strong>{displayName} conectado correctamente</strong> — integración <code>{code}</code> vinculada a tu cuenta. {publishText}</div>
    </div>
  )
}

function renderConnectErrorAlert(displayName: string, errorDetail: string | null) {
  return (
    <div role="alert" className="alert-custom alert-custom-danger mb-4">
      <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div className="alert-custom-content"><strong>Error al conectar {displayName}</strong> {errorDetail ? `— ${errorDetail}` : ''}. Intenta nuevamente.</div>
    </div>
  )
}

const PUBLISH_TEXT: Record<IntegrationPlatform, string> = {
  youtube: 'Ya puedes publicar clips en YouTube.',
  instagram: 'Ya puedes publicar Reels en Instagram.',
  tiktok: 'Ya puedes publicar clips en TikTok.',
}

function renderPlatformAlert(platform: IntegrationPlatform, status: string | null, errorDetail: string | null) {
  const name = DISPLAY_NAMES[platform]
  if (status === 'success') return renderConnectedAlert(name, platform, PUBLISH_TEXT[platform])
  if (status === 'error') return renderConnectErrorAlert(name, errorDetail)
  return null
}

function renderIntegrationAlert(integration: string | null, status: string | null, errorDetail: string | null) {
  if (integration === 'youtube') return renderPlatformAlert('youtube', status, errorDetail)
  if (integration === 'instagram') return renderPlatformAlert('instagram', status, errorDetail)
  if (integration === 'tiktok') return renderPlatformAlert('tiktok', status, errorDetail)
  return null
}

function renderErrorAlert(error: string | null) {
  if (!error) return null
  return (
    <div role="alert" className="alert-custom alert-custom-danger mb-4">
      <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div className="alert-custom-content">{error}</div>
    </div>
  )
}

function renderDisconnectButton(loading: boolean, onDisconnect: () => void, testId: string) {
  return (
    <button
      className="btn-custom w-full flex items-center justify-center gap-2 bg-transparent text-[#F87171] border border-[#F87171]/30 hover:bg-[#F87171]/10 mt-2"
      disabled={loading}
      data-testid={testId}
      onClick={onDisconnect}
    >
      <i className="bi bi-box-arrow-right" /> Desconectar
    </button>
  )
}

export default function IntegrationsPage() {
  const {
    integration, status, errorDetail, loading, error, social,
    handleConnectYoutube, handleConnectInstagram, handleConnectTiktok, handleDisconnect,
  } = useIntegrations()

  const youtubeConnected = platformConnected(social, integration, status, 'youtube')
  const instagramConnected = platformConnected(social, integration, status, 'instagram')
  const tiktokConnected = platformConnected(social, integration, status, 'tiktok')

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

      {renderIntegrationAlert(integration, status, errorDetail)}
      {renderErrorAlert(error)}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PlatformCard
          name="YouTube"
          icon="bi bi-youtube"
          iconWrapClass="h-10 w-10 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000] text-xl"
          connected={!!youtubeConnected}
          username={platformUsername(social, 'youtube')}
          description="Google Data API v3 — upload + readonly"
          descriptionLong="Conecta tu canal para subir clips directamente como Shorts. Scopes: youtube.readonly + youtube.upload"
          endpointHint="GET /auth/social/youtube/connect → redirect Google OAuth (offline + consent)"
          loading={loading}
          onConnect={handleConnectYoutube}
          connectLabel="Conectar YouTube"
          connectIcon="bi bi-box-arrow-up-right"
          connectClass="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2"
        >
          {youtubeConnected ? renderDisconnectButton(loading, () => handleDisconnect('youtube'), 'disconnect-youtube-btn') : null}
        </PlatformCard>

        <PlatformCard
          name="Instagram"
          icon="bi bi-instagram"
          iconWrapClass="h-10 w-10 rounded-xl bg-[#E1306C]/10 border border-[#E1306C]/20 flex items-center justify-center text-[#E1306C] text-xl"
          connected={!!instagramConnected}
          username={platformUsername(social, 'instagram')}
          description="Meta Graph API — instagram_basic + content_publish"
          descriptionLong="Conecta tu cuenta para publicar Reels automáticamente. Scopes: instagram_basic + instagram_content_publish + pages_show_list"
          endpointHint="GET /auth/social/instagram/connect → redirect Meta OAuth (long-lived 60 días)"
          loading={loading}
          onConnect={handleConnectInstagram}
          connectLabel="Conectar Instagram"
          connectIcon="bi bi-instagram"
          connectClass="btn-custom w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#F58529] via-[#DD2A7B] to-[#515BD4] text-white border-0 hover:opacity-90"
        >
          {instagramConnected ? renderDisconnectButton(loading, () => handleDisconnect('instagram'), 'disconnect-instagram-btn') : null}
        </PlatformCard>

        <PlatformCard
          name="TikTok"
          icon="bi bi-tiktok"
          iconWrapClass="h-10 w-10 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-white text-xl"
          connected={!!tiktokConnected}
          username={platformUsername(social, 'tiktok')}
          description="Content Posting API — FILE_UPLOAD + PKCE"
          descriptionLong="Conecta tu cuenta de TikTok para publicar clips automáticamente. OAuth 2.0 con PKCE (S256); los clips se suben como borrador SELF_ONLY desde la Content Posting API."
          endpointHint="GET /auth/social/tiktok/connect → redirect TikTok OAuth (PKCE S256)"
          loading={loading}
          onConnect={handleConnectTiktok}
          connectLabel="Conectar TikTok"
          connectIcon="bi bi-tiktok"
          connectClass="btn-custom w-full flex items-center justify-center gap-2 bg-black text-white border border-white/20 hover:opacity-90"
        >
          {tiktokConnected ? renderDisconnectButton(loading, () => handleDisconnect('tiktok'), 'disconnect-tiktok-btn') : null}
        </PlatformCard>
      </div>

      <div className="card-spark mt-4 bg-[#0B0F17]/50">
        <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2"><i className="bi bi-info-circle text-[#B4F105]" /> Cómo probar el flujo completo</h4>
        <ol className="list-decimal list-inside text-sm text-[#94A3B8] space-y-1">
          <li>Asegúrate de tener <code>GOOGLE_CLIENT_ID</code> / <code>GOOGLE_CLIENT_SECRET</code> (YouTube), <code>FACEBOOK_CLIENT_ID</code> / <code>FACEBOOK_CLIENT_SECRET</code> (Instagram) o <code>TIKTOK_CLIENT_KEY</code> / <code>TIKTOK_CLIENT_SECRET</code> (TikTok) en <code>.env</code></li>
          <li>Haz clic en <strong>Conectar</strong> en la tarjeta (llama a <code>GET /auth/social/&lt;plataforma&gt;/connect</code> con tu JWT)</li>
          <li>Serás redirigido al proveedor — acepta los scopes de publicación</li>
          <li>El proveedor redirige a <code>/auth/social/&lt;plataforma&gt;/callback?code=...&amp;state=...</code> → backend intercambia tokens → guarda en <code>social_accounts</code> → redirige aquí a <code>?integration=&lt;plataforma&gt;&amp;status=success</code></li>
          <li>Verifica en DB: <code>SELECT platform, platform_account_id FROM social_accounts</code></li>
        </ol>
      </div>
    </div>
  )
}
