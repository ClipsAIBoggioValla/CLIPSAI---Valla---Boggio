<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Avatar from '@/components/Avatar.vue'

defineProps<{ onToggleDesktop: () => void; onToggleMobile: () => void }>()

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const displayName = computed(() => (auth.user as unknown as { full_name?: string | null })?.full_name ?? null)
const avatarUrl = computed(() => (auth.user as unknown as { avatar_url?: string | null })?.avatar_url ?? null)
const firstName = computed(() => {
  const full = (auth.user as unknown as { full_name?: string | null })?.full_name
  if (full && full.trim()) return full.trim().split(' ')[0]
  return auth.user?.email?.split('@')[0] ?? 'Usuario'
})

const notifOpen = ref(false)
const quickOpen = ref(false)
const search = ref((route.query.q as string) ?? '')

const notifRef = ref<HTMLDivElement | null>(null)
const quickRef = ref<HTMLDivElement | null>(null)

function onDocClick(e: MouseEvent) {
  if (notifRef.value && !notifRef.value.contains(e.target as Node)) notifOpen.value = false
  if (quickRef.value && !quickRef.value.contains(e.target as Node)) quickOpen.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

watch(
  () => route.query.q,
  (q) => {
    if (route.path === '/clips' || route.path === '/library') {
      const v = (q as string) ?? ''
      if (v !== search.value) search.value = v
    }
  },
)

let debounceTimer: number | undefined
watch(search, (v) => {
  if (route.path !== '/clips' && route.path !== '/library') return
  window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    const trimmed = v.trim()
    const query: Record<string, string> = { ...(route.query as Record<string, string>) }
    if (trimmed) query.q = trimmed
    else delete query.q
    const currentQ = (route.query.q as string) ?? ''
    if ((trimmed ?? '') !== (currentQ ?? '')) router.replace({ path: route.path, query })
  }, 350)
})

function handleSearch() {
  const trimmed = search.value.trim()
  if (trimmed) router.push({ path: '/clips', query: { q: trimmed } })
  else router.push({ path: '/clips' })
}

function toggleFullscreen() {
  const doc = document as unknown as { fullscreenElement: Element | null; exitFullscreen?: () => Promise<void> }
  const el = document.documentElement as unknown as { requestFullscreen?: () => Promise<void> }
  if (doc.fullscreenElement) doc.exitFullscreen?.().catch(() => {})
  else el.requestFullscreen?.().catch(() => {})
}
</script>

<template>
  <header v-if="auth.isAuthenticated" class="navbar-custom">
    <div class="navbar-left">
      <button class="btn-desktop-toggle" type="button" aria-label="Minimizar Sidebar" @click="$props.onToggleDesktop">
        <i class="bi bi-chevron-bar-left" />
      </button>
      <button class="sidebar-toggle-btn" type="button" aria-label="Toggle Navigation" @click="$props.onToggleMobile">
        <i class="bi bi-list" />
      </button>

      <div ref="quickRef" class="dropdown" style="position: relative">
        <button class="btn-quick-action" type="button" :aria-expanded="quickOpen" @click="quickOpen = !quickOpen">
          <i class="bi bi-plus-lg" />
          <span>Crear</span>
        </button>
        <ul v-if="quickOpen" class="dropdown-menu dropdown-menu-quick-action show" style="display: block; position: absolute; top: 100%; left: 0">
          <li class="dropdown-header">Crear nuevo</li>
          <li><a class="dropdown-item" href="#" @click.prevent="quickOpen = false; router.push('/upload')"><i class="bi bi-cloud-arrow-up" /> Subir video</a></li>
        </ul>
      </div>
    </div>

    <div class="navbar-search-wrapper">
      <input v-model="search" type="text" class="navbar-search-input" placeholder="Buscar clips, videos..." aria-label="Buscar" @keydown.enter.prevent="handleSearch" />
      <button class="navbar-search-btn" aria-label="Buscar" type="button" @click="handleSearch"><i class="bi bi-search" /></button>
    </div>

    <div class="navbar-actions">
      <button class="navbar-action-btn" aria-label="Pantalla completa" type="button" @click="toggleFullscreen">
        <i class="bi bi-arrows-fullscreen" />
      </button>

      <div ref="notifRef" class="dropdown" style="position: relative">
        <button class="navbar-action-btn dropdown-toggle" type="button" :aria-expanded="notifOpen" @click="notifOpen = !notifOpen">
          <i class="bi bi-bell" />
          <span class="navbar-action-badge" />
        </button>
        <div v-if="notifOpen" class="dropdown-menu dropdown-menu-notification show" style="display: block; position: absolute; right: 0; top: 100%">
          <div class="notification-header">
            <h6 class="notification-title">Notificaciones</h6>
          </div>
          <div class="p-4 text-center">
            <div class="h-10 w-10 rounded-full flex items-center justify-center mx-auto mb-3" style="background: rgba(255,255,255,0.08); color: #94a3b8"><i class="bi bi-bell-slash" /></div>
            <p class="text-sm font-medium" style="color: #f1f5f9">No hay notificaciones por ahora</p>
            <p class="text-xs mt-1" style="color: #94a3b8">Cuando haya actividad verás aquí tus avisos.</p>
          </div>
        </div>
      </div>

      <div class="d-flex align-items-center gap-2" style="margin-left: 0.25rem">
        <Avatar :name="displayName" :email="auth.user?.email ?? null" :avatar-url="avatarUrl" :size="32" />
        <span class="d-none d-md-inline" style="color: var(--text-main); font-weight: 700; font-size: 0.85rem">{{ firstName }}</span>
      </div>
    </div>
  </header>
</template>
