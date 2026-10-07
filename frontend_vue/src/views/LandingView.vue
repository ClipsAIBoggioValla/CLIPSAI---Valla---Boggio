<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import LandingAbout from '@/components/landing/LandingAbout.vue'
import LandingFeatures from '@/components/landing/LandingFeatures.vue'
import LandingFooter from '@/components/landing/LandingFooter.vue'
import LandingHero from '@/components/landing/LandingHero.vue'
import LandingHowItWorks from '@/components/landing/LandingHowItWorks.vue'
import LandingNav from '@/components/landing/LandingNav.vue'
import { applyLandingSeo } from '@/components/landing/landingSeo'

/**
 * Landing pública de ClipsAI en `/` (Issue 32).
 *
 * - No requiere autenticación: es la anteportada para usuarios anónimos y para los
 *   revisores de Meta / Google / TikTok, que necesitan una URL pública con aviso
 *   de privacidad y contacto.
 * - Accible también con sesión activa: no redirige a /dashboard.
 */
onMounted(() => {
  applyLandingSeo()
})
</script>

<template>
  <div id="top" class="landing">
    <a href="#contenido" class="landing-skip-link">Saltar al contenido</a>
    <div class="landing-shell">
      <LandingNav />
      <main id="contenido" class="landing-main">
        <LandingHero />
        <LandingHowItWorks />
        <LandingAbout />
        <LandingFeatures />
        <section class="landing-container" aria-labelledby="cta-final-title">
          <div class="landing-cta-band">
            <h2 id="cta-final-title" class="landing-heading">
              Subí tu video y mirá <span class="landing-accent">qué clip sale primero</span>
            </h2>
            <p class="landing-lead">
              Creás la cuenta gratis, subís un video largo y en minutos tenés clips verticales con subtítulos,
              score de viralidad y publicación automática.
            </p>
            <div class="landing-cta-row landing-cta-row-center">
              <RouterLink to="/auth" class="landing-btn landing-btn-primary">
                Probar gratis <i class="bi bi-arrow-right" aria-hidden="true" />
              </RouterLink>
              <a href="#features" class="landing-btn landing-btn-ghost">Ver features</a>
            </div>
          </div>
        </section>
      </main>
      <LandingFooter />
    </div>
  </div>
</template>