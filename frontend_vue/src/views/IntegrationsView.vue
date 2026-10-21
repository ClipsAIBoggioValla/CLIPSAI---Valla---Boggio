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
    <div v-if="error" role="alert" class="alert-custom alert-custom-danger mb-4">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <PlatformCard name="YouTube" icon="bi bi-youtube" icon-wrap-class="h-10 w-10 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000] text-xl" :connected="social?.youtube.connected || (integration === 'youtube' && status === 'success')" :username="social?.youtube.username ?? null" description="Google Data API v3 — upload + readonly" description-long="Conecta tu canal para subir clips directamente como Shorts. Scopes: youtube.readonly + youtube.upload" endpoint-hint="GET /auth/social/youtube/connect → redirect Google OAuth (offline + consent)">
        <button class="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2" :disabled="loading" data-testid="connect-youtube-btn" @click="handleConnectYoutube">
          <span v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" />
          <template v-if="!loading"><i class="bi bi-box-arrow-up-right" /> Conectar YouTube</template>
          <template v-else>Conectando...</template>
        </button>
      </PlatformCard>

      <PlatformCard name="Instagram" icon="bi bi-instagram" icon-wrap-class="h-10 w-10 rounded-xl bg-[#E1306C]/10 border border-[#E1306C]/20 flex items-center justify-center text-[#E1306C] text-xl" :connected="social?.instagram.connected || (integration === 'instagram' && status === 'success')" :username="social?.instagram.username ?? null" description="Meta Graph API — instagram_basic + content_publish" description-long="Conecta tu cuenta para publicar Reels automáticamente. Scopes: instagram_basic + instagram_content_publish + pages_show_list" endpoint-hint="GET /auth/social/instagram/connect → redirect Meta OAuth (long-lived 60 días)">
        <button class="btn-custom w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#F58529] via-[#DD2A7B] to-[#515BD4] text-white border-0 hover:opacity-90" :disabled="loading" data-testid="connect-instagram-btn" @click="handleConnectInstagram">
          <span v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          <template v-if="!loading"><i class="bi bi-instagram" /> Conectar Instagram</template>
          <template v-else>Conectando...</template>
        </button>
      </PlatformCard>
    </div>

    <div class="card-spark mt-4 bg-[#0B0F17]/50">
      <h4 class="text-sm font-bold text-white mb-2 flex items-center gap-2"><i class="bi bi-info-circle text-[#B4F105]" /> Cómo probar el flujo completo</h4>
      <ol class="list-decimal list-inside text-sm text-[#94A3B8] space-y-1">
        <li>Asegúrate de tener <code>GOOGLE_CLIENT_ID</code> / <code>GOOGLE_CLIENT_SECRET</code> en <code>.env</code> y backend en <code>https://decorator-excretory-satin.ngrok-free.dev</code> o <code>http://localhost:8000</code></li>
        <li>Haz clic en <strong>Conectar YouTube</strong> arriba (llama a <code>GET /auth/social/youtube/connect</code> con tu JWT)</li>
        <li>Serás redirigido a <code>accounts.google.com</code> — acepta scopes <code>youtube.readonly</code> + <code>youtube.upload</code></li>
        <li>Google redirige a <code>/auth/social/youtube/callback?code=...&amp;state=...</code> → backend intercambia tokens → guarda en <code>social_accounts</code> → redirige aquí a <code>?integration=youtube&amp;status=success</code></li>
        <li>Verifica en DB: <code>SELECT platform, platform_account_id FROM social_accounts WHERE platform='youtube'</code></li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useIntegrations } from '@/composables/useIntegrations'
import PlatformCard from '@/components/integrations/PlatformCard.vue'

const {
  loading, error, integration, status, errorDetail, social, route, router,
  fetchSocialStatus, syncQuery, handleConnectYoutube, handleConnectInstagram,
} = useIntegrations()

import { onMounted } from 'vue'
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
</script>
EOF
echo "written ($(wc -l < frontend_vue/src/views/IntegrationsView.vue) lines)"