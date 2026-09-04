<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import Avatar from '@/components/Avatar.vue'

const auth = useAuthStore()
const router = useRouter()
const open = ref(false)
const refEl = ref<HTMLDivElement | null>(null)
const displayName = computed(() => ((auth.user as unknown as { full_name?: string | null })?.full_name ?? null))
const displayEmail = computed(() => auth.user?.email ?? null)

function onDocClick(e: MouseEvent) {
  if (refEl.value && !refEl.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

function handleLogout() {
  open.value = false
  auth.logout()
  router.replace('/auth')
}
function goSettings() {
  open.value = false
  router.push('/settings')
}
</script>

<template>
  <header v-if="auth.isAuthenticated" class="sticky top-0 z-40 bg-gray-900/80 backdrop-blur border-b border-gray-800">
    <div class="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
      <div class="flex items-center gap-6">
        <span class="text-white font-bold tracking-tight">clipsai</span>
        <nav class="flex items-center gap-1">
          <RouterLink
            to="/dashboard"
            :class="$route.path === '/dashboard' ? 'bg-violet-600 text-white font-bold px-3 py-2 rounded-lg shadow-sm' : 'text-slate-700 dark:text-slate-300 hover:text-slate-950 dark:hover:text-white font-semibold px-3 py-2 rounded-lg transition-colors'"
          >
            Dashboard
          </RouterLink>
          <RouterLink
            to="/clips"
            :class="$route.path === '/clips' ? 'bg-violet-600 text-white font-bold px-3 py-2 rounded-lg shadow-sm' : 'text-slate-700 dark:text-slate-300 hover:text-slate-950 dark:hover:text-white font-semibold px-3 py-2 rounded-lg transition-colors'"
          >
            Biblioteca
          </RouterLink>
          <RouterLink
            to="/upload"
            :class="$route.path === '/upload' ? 'bg-violet-600 text-white font-bold px-3 py-2 rounded-lg shadow-sm' : 'text-slate-700 dark:text-slate-300 hover:text-slate-950 dark:hover:text-white font-semibold px-3 py-2 rounded-lg transition-colors'"
          >
            Subir
          </RouterLink>
        </nav>
      </div>
      <div ref="refEl" class="relative">
        <button
          type="button"
          class="flex items-center gap-2 rounded-full border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 transition"
          aria-haspopup="menu"
          :aria-expanded="open"
          @click="open = !open"
        >
          <Avatar :name="displayName" :email="displayEmail" :size="28" />
          <span class="hidden sm:block text-xs font-medium text-slate-900 dark:text-white max-w-[160px] truncate">{{ displayEmail }}</span>
          <span :class="['text-slate-500 transition', open ? 'rotate-180' : '']">▾</span>
        </button>
        <div v-if="open" role="menu" class="absolute right-0 mt-2 w-64 origin-top-right rounded-xl border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg overflow-hidden z-30">
          <div class="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
            <p class="text-sm font-bold text-slate-900 dark:text-white truncate flex items-center gap-2"><Avatar :name="displayName" :email="displayEmail" :size="20" /> {{ displayEmail }}</p>
            <p class="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-1"><span class="h-2 w-2 rounded-full bg-emerald-500 inline-block" /> Sesión activa</p>
          </div>
          <button type="button" role="menuitem" class="w-full text-left px-4 py-2.5 text-sm font-medium text-slate-900 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-700 transition flex items-center gap-2" @click="goSettings">👤 Mi Perfil / Ajustes</button>
          <button type="button" role="menuitem" class="w-full text-left px-4 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition flex items-center gap-2 border-t border-slate-200 dark:border-slate-700" @click="handleLogout">↪ Cerrar sesión</button>
        </div>
      </div>
    </div>
  </header>
</template>
