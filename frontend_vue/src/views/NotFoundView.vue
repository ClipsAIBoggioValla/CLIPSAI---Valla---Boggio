<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="login-wrapper">
    <div class="login-bg-shape login-bg-shape-1" />
    <div class="login-bg-shape login-bg-shape-2" />

    <div class="login-card text-center">
      <a href="#" class="login-brand" @click.prevent="router.push('/dashboard')">
        <i class="bi bi-asterisk" />
        <span>clipsai</span>
      </a>

      <div class="error-title-huge">
        <span>4</span>
        <i class="bi bi-asterisk" />
        <span>4</span>
      </div>

      <h2 class="error-subtitle">Página No Encontrada</h2>
      <p class="error-desc">La página que buscas puede haber sido eliminada, cambió de nombre o no está disponible temporalmente.</p>

      <div class="error-actions-group">
        <RouterLink to="/dashboard" class="btn-custom btn-custom-primary">
          <i class="bi bi-house" /> Volver al Dashboard
        </RouterLink>
        <RouterLink to="/upload" class="btn-custom btn-custom-light"> Subir video</RouterLink>
      </div>
    </div>
  </div>
</template>
