<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { HERO_STATS } from './landingData'

const WAVE_BARS = Array.from({ length: 26 }, (_, i) => i)

const PIPELINE = [
  { icon: 'bi-soundwave', label: 'Audio analizado: 50 momentos' },
  { icon: 'bi-stars', label: 'IA: 10 clips con score' },
  { icon: 'bi-phone', label: 'Render 9:16 + subtítulos ASS' },
  { icon: 'bi-send-check', label: 'Publicado en 3 redes' },
]
</script>

<template>
  <section class="landing-hero" aria-labelledby="hero-title">
    <div class="landing-container landing-hero-grid">
      <div>
        <span class="landing-eyebrow">
          <i class="bi bi-stars" aria-hidden="true" /> Motor IA propio · audio real · autopublicación
        </span>
        <h1 id="hero-title" class="landing-heading">
          De un video largo a <span class="landing-accent">clips que se publican solos</span>
        </h1>
        <p class="landing-lead">
          ClipsAI escucha el audio de tu video, encuentra con IA los momentos que enganchan, los corta en vertical
          9:16 con subtítulos palabra por palabra y los publica en YouTube, Instagram y TikTok. Sin editor, sin
          exportar a mano, sin posts que quedan en el borrador.
        </p>
        <div class="landing-cta-row">
          <RouterLink to="/auth" class="landing-btn landing-btn-primary">
            Probar gratis <i class="bi bi-arrow-right" aria-hidden="true" />
          </RouterLink>
          <a href="#como-funciona" class="landing-btn landing-btn-ghost">
            <i class="bi bi-play-circle" aria-hidden="true" /> Ver cómo funciona
          </a>
        </div>
        <p class="landing-cta-note">
          <i class="bi bi-shield-check" aria-hidden="true" /> Sin tarjeta de crédito · tu video solo se usa para
          generar tus clips
        </p>
      </div>

      <div class="landing-hero-visual" aria-hidden="true">
        <div class="landing-hero-badge"><i class="bi bi-graph-up-arrow" /> +38 % retención</div>
        <div class="landing-phone">
          <div class="landing-phone-top">
            <span class="landing-chip">SCORE 9.1</span>
            <span>0:46 · 9:16</span>
          </div>
          <div class="landing-phone-screen">
            <div class="landing-wave">
              <span v-for="i in WAVE_BARS" :key="i" :style="{ animationDelay: `${(i % 9) * 0.12}s` }" />
            </div>
            <p class="landing-phone-sub">nadie te dice <em>esto</em></p>
          </div>
          <div>
            <div class="landing-phone-bar"><span style="width: 82%" /></div>
            <div class="landing-phone-pipeline">
              <span v-for="item in PIPELINE" :key="item.label">
                <i class="bi" :class="item.icon" /> {{ item.label }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="landing-container">
      <dl class="landing-stats">
        <div v-for="stat in HERO_STATS" :key="stat.label">
          <dd class="landing-stat-value">{{ stat.value }}</dd>
          <dt class="landing-stat-label">{{ stat.label }}</dt>
        </div>
      </dl>
    </div>
  </section>
</template>