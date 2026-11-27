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

function renderConnectedAlert(displayName: string, publishText: string) {
  return (
    <div role="alert" className="alert-custom alert-custom-success mb-4">
      <i className="bi bi-check-circle-fill alert-custom-icon" />
      <div className="alert-custom-content"><strong>{displayName} está conectado.</strong> {publishText}</div>
    </div>
  )
}

function renderConnectErrorAlert(displayName: string) {
  return (
    <div role="alert" className="alert-custom alert-custom-danger mb-4">
      <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div className="alert-custom-content"><strong>No pudimos conectar {displayName}.</strong> Intenta nuevamente.</div>
    </div>
  )
}

const PUBLISH_TEXT: Record<IntegrationPlatform, string> = {
  youtube: 'Tu canal está listo para compartir clips como Shorts.',
  instagram: 'Tu cuenta está lista para compartir Reels.',
  tiktok: 'Tus clips se enviarán como borradores para que los revises en TikTok.',
}

function renderPlatformAlert(platform: IntegrationPlatform, status: string | null) {
  const name = DISPLAY_NAMES[platform]
  if (status === 'success') return renderConnectedAlert(name, PUBLISH_TEXT[platform])
  if (status === 'error') return renderConnectErrorAlert(name)
  return null
}

function renderIntegrationAlert(integration: string | null, status: string | null) {
  if (integration === 'youtube') return renderPlatformAlert('youtube', status)
  if (integration === 'instagram') return renderPlatformAlert('instagram', status)
  if (integration === 'tiktok') return renderPlatformAlert('tiktok', status)
  return null
}

function renderErrorAlert(error: string | null) {
  if (!error) return null
  return (
    <div role="alert" className="alert-custom alert-custom-danger mb-4">
      <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div className="alert-custom-content">No pudimos cargar tus conexiones. Intenta actualizar la página.</div>
    </div>
  )
}

function renderDisconnectButton(loading: boolean, onDisconnect: () => void, testId: string) {
  return (
    <button
      className="btn-custom btn-custom-danger w-full flex items-center justify-center gap-2 mt-2"
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
    integration, status, loading, error, social,
    handleConnectYoutube, handleConnectInstagram, handleConnectTiktok, handleDisconnect,
  } = useIntegrations()

  const youtubeConnected = platformConnected(social, integration, status, 'youtube')
  const instagramConnected = platformConnected(social, integration, status, 'instagram')
  const tiktokConnected = platformConnected(social, integration, status, 'tiktok')

  return (
    <div className="max-w-4xl mx-auto">
      <div className="page-header mb-8">
        <div className="flex items-center gap-4">
          <span className="dropzone-icon-neon shrink-0">
            <i className="bi bi-share" />
          </span>
          <div>
            <h1 className="page-title mb-0 text-4xl font-extrabold tracking-tight">Tus redes</h1>
            <p className="page-subtitle mb-0 text-sm">Conecta tus cuentas para compartir tus clips.</p>
          </div>
        </div>
      </div>

      {renderIntegrationAlert(integration, status)}
      {renderErrorAlert(error)}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PlatformCard
          name="YouTube"
          icon="bi bi-youtube"
          iconWrapClass="kpi-accent shrink-0 text-lg"
          connected={!!youtubeConnected}
          username={platformUsername(social, 'youtube')}
          description="Comparte tus clips como YouTube Shorts"
          descriptionLong="Conecta tu canal para subir clips en formato Shorts."
          endpointHint="Autoriza la conexión en la página oficial de YouTube."
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
          iconWrapClass="kpi-accent shrink-0 text-lg"
          connected={!!instagramConnected}
          username={platformUsername(social, 'instagram')}
          description="Comparte tus clips como Reels"
          descriptionLong="Conecta tu cuenta de Instagram para publicar Reels desde ClipsAI."
          endpointHint="Autoriza la conexión en la página oficial de Instagram."
          loading={loading}
          onConnect={handleConnectInstagram}
          connectLabel="Conectar Instagram"
          connectIcon="bi bi-instagram"
          connectClass="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2"
        >
          {instagramConnected ? renderDisconnectButton(loading, () => handleDisconnect('instagram'), 'disconnect-instagram-btn') : null}
        </PlatformCard>

        <PlatformCard
          name="TikTok"
          icon="bi bi-tiktok"
          iconWrapClass="kpi-accent shrink-0 text-lg"
          connected={!!tiktokConnected}
          username={platformUsername(social, 'tiktok')}
          description="Comparte tus clips en TikTok"
          descriptionLong="Conecta TikTok para enviar tus clips como borradores y revisarlos antes de publicar."
          endpointHint="Autoriza la conexión en la página oficial de TikTok."
          loading={loading}
          onConnect={handleConnectTiktok}
          connectLabel="Conectar TikTok"
          connectIcon="bi bi-tiktok"
          connectClass="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2"
        >
          {tiktokConnected ? renderDisconnectButton(loading, () => handleDisconnect('tiktok'), 'disconnect-tiktok-btn') : null}
        </PlatformCard>
      </div>

      <div className="card-spark mt-4">
        <h2 className="text-sm font-bold text-[var(--text-primary)] mb-3 flex items-center gap-2"><i className="bi bi-info-circle text-[var(--brand-lime)]" /> Cómo conectar tus cuentas</h2>
        <ol className="list-decimal list-inside text-sm text-[var(--text-secondary)] space-y-2">
          <li>Elige la red que quieres conectar.</li>
          <li>Autoriza el acceso en la página oficial de esa red.</li>
          <li>Al volver a ClipsAI, verás tu cuenta como conectada.</li>
        </ol>
      </div>
    </div>
  )
}
