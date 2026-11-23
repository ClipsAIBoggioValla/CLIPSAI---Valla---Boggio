<script setup lang="ts">
import { LANDING_ABOUT, LANDING_STACK } from './landingData'
</script>

<template>
  <section id="sobre-nosotros" class="landing-section" aria-labelledby="sobre-nosotros-title">
    <div class="landing-container">
      <div class="landing-section-head">
        <span class="landing-eyebrow"><i class="bi bi-code-slash" aria-hidden="true" /> Sobre nosotros</span>
        <h2 id="sobre-nosotros-title" class="landing-heading">
          El motor por debajo <span class="landing-accent">del botón</span>
        </h2>
        <p class="landing-lead">
          ClipsAI no es una caja negra: escribimos el pipeline completo —audio, prompt, scoring, render y
          publicación— y lo auditamos en cada job.
        </p>
      </div>

      <div class="landing-about-grid">
        <article v-for="pillar in LANDING_ABOUT" :key="pillar.title" class="landing-about-card">
          <span class="landing-about-icon" aria-hidden="true"><i class="bi" :class="pillar.icon" /></span>
          <h3 class="landing-about-title">{{ pillar.title }}</h3>
          <p class="landing-about-text">{{ pillar.text }}</p>
          <code class="landing-about-code">{{ pillar.code }}</code>
        </article>
      </div>

      <div class="landing-stack" aria-label="Stack tecnológico de ClipsAI">
        <span v-for="tech in LANDING_STACK" :key="tech">{{ tech }}</span>
      </div>
    </div>
  </section>
</template>