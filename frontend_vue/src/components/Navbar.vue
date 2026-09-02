<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

function handleLogout() {
  auth.logout()
  router.replace('/auth')
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
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/dashboard' ? 'bg-violet-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'"
          >
            Dashboard
          </RouterLink>
          <RouterLink
            to="/clips"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/clips' ? 'bg-violet-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'"
          >
            Biblioteca
          </RouterLink>
          <RouterLink
            to="/upload"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === '/upload' ? 'bg-violet-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'"
          >
            Subir
          </RouterLink>
        </nav>
      </div>
      <div class="flex items-center gap-3">
        <span class="hidden sm:block text-xs text-gray-400 max-w-[160px] truncate">{{ auth.user?.email }}</span>
        <button
          class="text-xs font-medium text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 rounded-lg px-3 py-1.5 transition"
          @click="handleLogout"
        >
          Cerrar sesión
        </button>
      </div>
    </div>
  </header>
</template>
