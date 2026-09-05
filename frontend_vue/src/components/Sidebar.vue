<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import Avatar from '@/components/Avatar.vue'

defineProps<{ mobileOpen: boolean }>()
const emit = defineEmits<{ close: [] }>()
const auth = useAuthStore()

const sidebarName = computed(() => (auth.user as unknown as { full_name?: string | null })?.full_name ?? auth.user?.email?.split('@')[0] ?? 'Usuario')
const sidebarEmail = computed(() => auth.user?.email ?? 'invitado@clipsai')
const avatarUrl = computed(() => (auth.user as unknown as { avatar_url?: string | null })?.avatar_url ?? null)

const profileOpen = ref(false)
const profileRef = ref<HTMLDivElement | null>(null)

function onDocClick(e: MouseEvent) {
  if (profileRef.value && !profileRef.value.contains(e.target as Node)) profileOpen.value = false
}
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') profileOpen.value = false
}
onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  document.addEventListener('keydown', onEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  document.removeEventListener('keydown', onEsc)
})

function handleLogout() {
  profileOpen.value = false
  auth.logout()
  window.location.href = '/auth'
}
</script>

<template>
  <div :class="['sidebar-wrapper', { show: mobileOpen }]" id="sidebar">
    <RouterLink to="/dashboard" class="sidebar-brand" @click="emit('close')">
      <i class="bi bi-asterisk" />
      <span>clipsai</span>
    </RouterLink>

    <div class="flex-grow-1 overflow-y-auto">
      <div class="sidebar-menu-section">
        <div class="sidebar-menu-title">Menu</div>
        <ul class="sidebar-menu-list">
          <li class="sidebar-menu-item">
            <RouterLink to="/dashboard" class="sidebar-menu-link" active-class="active" @click="emit('close')">
              <i class="bi bi-grid-fill" />
              <span>Dashboard</span>
            </RouterLink>
          </li>
          <li class="sidebar-menu-item">
            <RouterLink to="/clips" class="sidebar-menu-link" active-class="active" @click="emit('close')">
              <i class="bi bi-collection-play" />
              <span>Biblioteca</span>
            </RouterLink>
          </li>
          <li class="sidebar-menu-item">
            <RouterLink to="/upload" class="sidebar-menu-link" active-class="active" @click="emit('close')">
              <i class="bi bi-cloud-arrow-up" />
              <span>Subir Video</span>
            </RouterLink>
          </li>
        </ul>
      </div>

      <div class="sidebar-menu-section">
        <div class="sidebar-menu-title">Páginas</div>
        <ul class="sidebar-menu-list">
          <li class="sidebar-menu-item">
            <RouterLink to="/settings" class="sidebar-menu-link" active-class="active" @click="emit('close')">
              <i class="bi bi-gear" />
              <span>Ajustes</span>
            </RouterLink>
          </li>
        </ul>
      </div>
    </div>

    <div
      ref="profileRef"
      class="sidebar-profile"
      role="button"
      tabindex="0"
      aria-haspopup="menu"
      :aria-expanded="profileOpen"
      style="position: relative; cursor: pointer"
      @click="profileOpen = !profileOpen"
      @keydown.enter.prevent="profileOpen = !profileOpen"
      @keydown.space.prevent="profileOpen = !profileOpen"
    >
      <Avatar :name="sidebarName" :email="sidebarEmail" :avatar-url="avatarUrl" :size="42" class="sidebar-profile-img" />
      <div class="sidebar-profile-info">
        <div class="sidebar-profile-name">{{ sidebarName }}</div>
        <div class="sidebar-profile-email">{{ sidebarEmail }}</div>
      </div>
      <i class="bi bi-chevron-up" style="color: var(--text-sidebar-muted); font-size: 0.75rem; transition: transform 0.2s; margin-left: auto" :style="{ transform: profileOpen ? 'rotate(180deg)' : 'rotate(0deg)' }" />
      <ul
        v-if="profileOpen"
        class="dropdown-menu dropdown-menu-profile show"
        style="display: block; position: absolute; bottom: 100%; top: auto; left: 0; right: auto; min-width: 240px; margin-bottom: 8px; z-index: 1060"
      >
        <li class="dropdown-header">¡Bienvenido!</li>
        <li><a class="dropdown-item" href="#" @click.prevent="profileOpen = false; $router.push('/settings')"><i class="bi bi-person" /> Mi Cuenta</a></li>
        <li><a class="dropdown-item" href="#" @click.prevent="profileOpen = false; $router.push('/settings')"><i class="bi bi-gear" /> Ajustes</a></li>
        <li><hr class="dropdown-divider" /></li>
        <li><a class="dropdown-item text-danger" href="#" @click.prevent="handleLogout"><i class="bi bi-box-arrow-right" /> Cerrar sesión</a></li>
      </ul>
    </div>
  </div>

  <div :class="['sidebar-overlay', { show: mobileOpen }]" @click="emit('close')" />
</template>
