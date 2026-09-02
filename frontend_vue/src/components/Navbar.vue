<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()
const open = ref(false)
const menuRef = ref<HTMLDivElement | null>(null)

function handleLogout() {
  auth.logout()
  router.replace('/auth')
}

function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('mousedown', onClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', onClickOutside))
</script>

<template>
  <header v-if="auth.isAuthenticated" class="sticky top-0 z-50 bg-white dark:bg-slate-900 border-b-2 border-slate-200 dark:border-slate-800">
    <div class="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
      <div class="flex items-center gap-6">
        <span class="text-slate-900 dark:text-white font-bold tracking-tight">clipsai</span>
        <nav class="flex items-center gap-1">
          <RouterLink
            to="/dashboard"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/dashboard' ? 'bg-violet-600 text-white font-bold shadow-md' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800'"
          >
            Dashboard
          </RouterLink>
          <RouterLink
            to="/clips"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/clips' ? 'bg-violet-600 text-white font-bold shadow-md' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800'"
          >
            Biblioteca
          </RouterLink>
          <RouterLink
            to="/upload"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/upload' ? 'bg-violet-600 text-white font-bold shadow-md' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800'"
          >
            Subir
          </RouterLink>
        </nav>
      </div>
      <div ref="menuRef" class="relative flex items-center gap-3">
        <span class="hidden sm:block text-xs text-slate-700 dark:text-slate-300 max-w-[160px] truncate">{{ auth.user?.email }}</span>
        <button class="h-8 w-8 rounded-full bg-violet-600 text-white font-bold shadow-md text-sm font-bold flex items-center justify-center" @click="open = !open" aria-haspopup="menu" :aria-expanded="open">
          {{ (auth.user?.email ? auth.user.email.charAt(0) : '?').toUpperCase() }}
        </button>
        <div v-if="open" class="absolute right-0 top-10 w-48 rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm shadow-xl py-1.5 z-50">
          <div class="px-4 py-2 border-b border-slate-200 dark:border-slate-700">
            <p class="text-xs font-medium text-slate-900 dark:text-white truncate">{{ auth.user?.email }}</p>
            <p class="text-xs text-slate-700 dark:text-slate-300 truncate">{{ auth.user?.full_name || 'Usuario' }}</p>
          </div>
          <button class="w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800 transition" @click="open=false; router.push('/settings')">Ajustes</button>
          <button class="w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800 transition" @click="open=false; router.push('/settings')">Perfil</button>
          <div class="border-t border-slate-200 dark:border-slate-700 my-1" />
          <button class="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-300 hover:text-red-700 dark:hover:text-red-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition" @click="handleLogout">Cerrar sesión</button>
        </div>
      </div>
    </div>
  </header>
</template>
