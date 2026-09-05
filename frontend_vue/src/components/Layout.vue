<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Sidebar from '@/components/Sidebar.vue'
import Navbar from '@/components/Navbar.vue'
import Footer from '@/components/Footer.vue'

const auth = useAuthStore()
const route = useRoute()
const minimized = ref(false)
const mobileOpen = ref(false)

watch(minimized, (v) => {
  if (v) document.body.classList.add('sidebar-minimized')
  else document.body.classList.remove('sidebar-minimized')
})

onMounted(() => {
  if (minimized.value) document.body.classList.add('sidebar-minimized')
})

function onToggleDesktop() {
  minimized.value = !minimized.value
}
function onToggleMobile() {
  mobileOpen.value = !mobileOpen.value
}
</script>

<template>
  <template v-if="auth.isAuthenticated && route.path !== '/404' && route.name !== 'notfound' && route.path !== '/auth'">
    <Sidebar :mobile-open="mobileOpen" @close="mobileOpen = false" />
    <div class="main-wrapper">
      <Navbar :on-toggle-desktop="onToggleDesktop" :on-toggle-mobile="onToggleMobile" />
      <div class="flex-grow-1">
        <RouterView />
      </div>
      <Footer />
    </div>
  </template>
  <template v-else>
    <RouterView />
  </template>
</template>
