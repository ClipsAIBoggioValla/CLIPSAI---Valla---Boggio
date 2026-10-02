<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { LANDING_NAV_LINKS } from './landingData'
</script>

<template>
  <header class="landing-nav">
    <div class="landing-container landing-nav-inner">
      <a href="#top" class="landing-brand" aria-label="ClipsAI — volver al inicio">
        <i class="bi bi-asterisk" aria-hidden="true" /> clipsai
      </a>
      <nav class="landing-nav-links" aria-label="Secciones de ClipsAI">
        <a v-for="link in LANDING_NAV_LINKS" :key="link.href + link.label" :href="link.href" class="landing-nav-link">
          {{ link.label }}
        </a>
      </nav>
      <div class="landing-nav-actions">
        <RouterLink to="/auth" class="landing-btn landing-btn-primary"> Probar gratis </RouterLink>
      </div>
    </div>
  </header>
</template>