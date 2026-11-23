<template>
  <div class="max-w-4xl mx-auto">
    <div class="page-header" style="margin-bottom: 2rem">
      <div class="flex items-center gap-4">
        <span class="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#FF0000] text-white border border-[rgba(255,0,0,0.3)] shadow-[0_0_16px_rgba(255,0,0,0.35)]"><i class="bi bi-youtube" style="font-size: 1.5rem" /></span>
        <div>
          <h1 class="page-title" style="margin-bottom: 0; font-size: 2.35rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; color: #F1F5F9">Integraciones</h1>
          <p class="page-subtitle" style="margin-bottom: 0; font-size: 0.98rem; font-weight: 500; color: #94A3B8; line-height: 1.6">Conecta tus redes sociales para publicación automática</p>
        </div>
      </div>
    </div>

    <div v-if="integration === 'youtube' && status === 'success'" role="alert" class="alert-custom alert-custom-success mb-4">
      <i class="bi bi-check-circle-fill alert-custom-icon" />
      <div class="alert-custom-content"><strong>YouTube conectado correctamente</strong> — integración <code>youtube</code> vinculada a tu cuenta. Ya puedes publicar clips en YouTube.</div>
    </div>
    <div v-if="integration === 'youtube' && status === 'error'" role="alert" class="alert-custom alert-custom-danger mb-4">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content"><strong>Error al conectar YouTube</strong> {{ errorDetail ? `— ${errorDetail}` : '' }}. Intenta nuevamente.</div>
    </div>
    <div v-if="integration === 'instagram' && status === 'success'" role="alert" class="alert-custom alert-custom-success mb-4">
      <i class="bi bi-check-circle-fill alert-custom-icon" />
      <div class="alert-custom-content"><strong>Instagram conectado correctamente</strong> — integración <code>instagram</code> vinculada a tu cuenta. Ya puedes publicar Reels en Instagram.</div>
    </div>
    <div v-if="integration === 'instagram' && status === 'error'" role="alert" class="alert-custom alert-custom-danger mb-4">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content"><strong>Error al conectar Instagram</strong> {{ errorDetail ? `— ${errorDetail}` : '' }}. Intenta nuevamente.</div>
    </div>
    <div v-if="integration === 'tiktok' && status === 'success'" role="alert" class="alert-custom alert-custom-success mb-4">
      <i class="bi bi-check-circle-fill alert-custom-icon" />
      <div class="alert-custom-content"><strong>TikTok conectado correctamente</strong> — integración <code>tiktok</code> vinculada a tu cuenta. Ya puedes publicar clips en TikTok.</div>
    </div>
    <div v-if="integration === 'tiktok' && status === 'error'" role="alert" class="alert-custom alert-custom-danger mb-4">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content"><strong>Error al conectar TikTok</strong> {{ errorDetail ? `— ${errorDetail}` : '' }}. Intenta nuevamente.</div>
    </div>
    <div v-if="error" role="alert" class="alert-custom alert-custom-danger mb-4">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <PlatformCard name="YouTube" icon="bi bi-youtube" icon-wrap-class="h-10 w-10 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000] text-xl" :connected="youtubeConnected" :username="social?.youtube.username ?? null" description="Google Data API v3 — upload + readonly" description-long="Conecta tu canal para subir clips directamente como Shorts. Scopes: youtube.readonly + youtube.upload" endpoint-hint="GET /auth/social/youtube/connect → redirect Google OAuth (offline + consent)">
        <button class="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2" :disabled="loading" data-testid="connect-youtube-btn" @click="handleConnectYoutube">
          <span v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" />
          <template v-if="!loading"><i class="bi bi-box-arrow-up-right" /> Conectar YouTube</template>
          <template v-else>Conectando...</template>
        </button>
        <button v-if="youtubeConnected" class="btn-custom w-full flex items-center justify-center gap-2 bg-transparent text-[#F87171] border border-[#F87171]/30 hover:bg-[#F87171]/10 mt-2" :disabled="loading" data-testid="disconnect-youtube-btn" @click="handleDisconnect('youtube')">
          <i class="bi bi-box-arrow-right" /> Desconectar
        </button>
      </PlatformCard>

      <PlatformCard name="Instagram" icon="bi bi-instagram" icon-wrap-class="h-10 w-10 rounded-xl bg-[#E1306C]/10 border border-[#E1306C]/20 flex items-center justify-center text-[#E1306C] text-xl" :connected="instagramConnected" :username="social?.instagram.username ?? null" description="Meta Graph API — instagram_basic + content_publish" description-long="Conecta tu cuenta para publicar Reels automáticamente. Scopes: instagram_basic + instagram_content_publish + pages_show_list" endpoint-hint="GET /auth/social/instagram/connect → redirect Meta OAuth (long-lived 60 días)">
        <button class="btn-custom w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#F58529] via-[#DD2A7B] to-[#515BD4] text-white border-0 hover:opacity-90" :disabled="loading" data-testid="connect-instagram-btn" @click="handleConnectInstagram">
          <span v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          <template v-if="!loading"><i class="bi bi-instagram" /> Conectar Instagram</template>
          <template v-else>Conectando...</template>
        </button>
        <button v-if="instagramConnected" class="btn-custom w-full flex items-center justify-center gap-2 bg-transparent text-[#F87171] border border-[#F87171]/30 hover:bg-[#F87171]/10 mt-2" :disabled="loading" data-testid="disconnect-instagram-btn" @click="handleDisconnect('instagram')">
          <i class="bi bi-box-arrow-right" /> Desconectar
        </button>
      </PlatformCard>

      <PlatformCard name="TikTok" icon="bi bi-tiktok" icon-wrap-class="h-10 w-10 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-white text-xl" :connected="tiktokConnected" :username="social?.tiktok.username ?? null" description="Content Posting API — FILE_UPLOAD + PKCE" description-long="Conecta tu cuenta de TikTok para publicar clips automáticamente. OAuth 2.0 con PKCE (S256); los clips se suben como borrador SELF_ONLY desde la Content Posting API." endpoint-hint="GET /auth/social/tiktok/connect → redirect TikTok OAuth (PKCE S256)">
        <button class="btn-custom w-full flex items-center justify-center gap-2 bg-black text-white border border-white/20 hover:opacity-90" :disabled="loading" data-testid="connect-tiktok-btn" @click="handleConnectTiktok">
          <span v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          <template v-if="!loading"><i class="bi bi-tiktok" /> Conectar TikTok</template>
          <template v-else>Conectando...</template>
        </button>
        <button v-if="tiktokConnected" class="btn-custom w-full flex items-center justify-center gap-2 bg-transparent text-[#F87171] border border-[#F87171]/30 hover:bg-[#F87171]/10 mt-2" :disabled="loading" data-testid="disconnect-tiktok-btn" @click="handleDisconnect('tiktok')">
          <i class="bi bi-box-arrow-right" /> Desconectar
        </button>
      </PlatformCard>
    </div>

    <div class="card-spark mt-4 bg-[#0B0F17]/50">
      <h4 class="text-sm font-bold text-white mb-2 flex items-center gap-2"><i class="bi bi-info-circle text-[#B4F105]" /> Cómo probar el flujo completo</h4>
      <ol class="list-decimal list-inside text-sm text-[#94A3B8] space-y-1">
        <li>Asegúrate de tener <code>GOOGLE_CLIENT_ID</code> / <code>GOOGLE_CLIENT_SECRET</code> (YouTube), <code>FACEBOOK_CLIENT_ID</code> / <code>FACEBOOK_CLIENT_SECRET</code> (Instagram) o <code>TIKTOK_CLIENT_KEY</code> / <code>TIKTOK_CLIENT_SECRET</code> (TikTok) en <code>.env</code></li>
        <li>Haz clic en <strong>Conectar</strong> en la tarjeta (llama a <code>GET /auth/social/&lt;plataforma&gt;/connect</code> con tu JWT)</li>
        <li>Serás redirigido al proveedor — acepta los scopes de publicación</li>
        <li>El proveedor redirige a <code>/auth/social/&lt;plataforma&gt;/callback?code=...&amp;state=...</code> → backend intercambia tokens → guarda en <code>social_accounts</code> → redirige aquí a <code>?integration=&lt;plataforma&gt;&amp;status=success</code></li>
        <li>Verifica en DB: <code>SELECT platform, platform_account_id FROM social_accounts</code></li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useIntegrations } from '@/composables/useIntegrations'
import PlatformCard from '@/components/integrations/PlatformCard.vue'

const {
  loading, error, integration, status, errorDetail, social,
  handleConnectYoutube, handleConnectInstagram, handleConnectTiktok, handleDisconnect,
} = useIntegrations()

type SocialEntry = { connected: boolean; username: string | null; expires_at: string | null }
type IntegrationPlatform = 'youtube' | 'instagram' | 'tiktok'

function conectada(social: { youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry } | null, platform: IntegrationPlatform, integration: string | null, status: string | null): boolean {
  return Boolean(social?.[platform].connected || (integration === platform && status === 'success'))
}

const youtubeConnected = computed(() => conectada(social.value, 'youtube', integration.value, status.value))
const instagramConnected = computed(() => conectada(social.value, 'instagram', integration.value, status.value))
const tiktokConnected = computed(() => conectada(social.value, 'tiktok', integration.value, status.value))
</script>
