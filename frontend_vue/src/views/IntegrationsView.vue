<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '@/api/client'
import { ApiError } from '@/types/api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const error = ref<string | null>(null)

const integration = ref<string | null>(null)
const status = ref<string | null>(null)
const errorDetail = ref<string | null>(null)

function syncQuery() {
  integration.value = route.query.integration as string | null
  status.value = route.query.status as string | null
  errorDetail.value = route.query.error as string | null
}

onMounted(() => {
  syncQuery()
  if (status.value) {
    setTimeout(() => {
      const q = { ...route.query }
      delete q.integration
      delete q.status
      delete q.error
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
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="page-header" style="margin-bottom: 2rem">
      <div class="flex items-center gap-4">
        <span class="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#FF0000] text-white border border-[rgba(255,0,0,0.3)] shadow-[0_0_16px_rgba(255,0,0,0.35)]">
          <i class="bi bi-youtube" style="font-size: 1.5rem" />
        </span>
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
    <div v-if="error" role="alert" class="alert-custom alert-custom-danger mb-4">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="card-spark">
        <div class="flex items-center gap-3 mb-3">
          <span class="h-10 w-10 rounded-xl bg-[#FF0000]/10 border border-[#FF0000]/20 flex items-center justify-center text-[#FF0000] text-xl"><i class="bi bi-youtube" /></span>
          <div>
            <h3 class="font-bold text-white">YouTube</h3>
            <p class="text-xs text-[#94A3B8]">Google Data API v3 — upload + readonly</p>
          </div>
          <span v-if="integration === 'youtube' && status === 'success'" class="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20"><span class="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado</span>
          <span v-else class="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-white/5 text-[#94A3B8] border border-white/10">No conectado</span>
        </div>
        <p class="text-sm text-[#94A3B8] mb-4">Conecta tu canal para subir clips directamente como Shorts. Scopes: <code class="text-xs bg-white/5 px-1 py-0.5 rounded">youtube.readonly</code> + <code class="text-xs bg-white/5 px-1 py-0.5 rounded">youtube.upload</code></p>
        <button class="btn-custom btn-custom-primary w-full flex items-center justify-center gap-2" :disabled="loading" data-testid="connect-youtube-btn" @click="handleConnectYoutube">
          <span v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-[#080C14]/30 border-t-[#080C14]" /> 
          <template v-if="!loading"><i class="bi bi-box-arrow-up-right" /> Conectar YouTube</template>
          <template v-else>Conectando...</template>
        </button>
        <p class="text-xs text-[#64748B] mt-2 text-center">GET <code>/auth/social/youtube/connect</code> → redirect Google OAuth (offline + consent)</p>
      </div>

      <div class="card-spark opacity-60">
        <div class="flex items-center gap-3 mb-3">
          <span class="h-10 w-10 rounded-xl bg-[#E1306C]/10 border border-[#E1306C]/20 flex items-center justify-center text-[#E1306C] text-xl"><i class="bi bi-instagram" /></span>
          <div>
            <h3 class="font-bold text-white">Instagram</h3>
            <p class="text-xs text-[#94A3B8]">Próximamente</p>
          </div>
          <span class="ml-auto text-xs px-2 py-1 rounded-full bg-white/5 border border-white/10 text-[#64748B]">Pronto</span>
        </div>
        <p class="text-sm text-[#64748B] mb-4">Publicación en Reels — en desarrollo.</p>
        <button disabled class="btn-custom btn-custom-light w-full opacity-50 cursor-not-allowed">Conectar Instagram</button>
      </div>
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
