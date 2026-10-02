<script setup lang="ts">
import { LANDING_FEATURES } from './landingData'
</script>

<template>
  <section id="features" class="landing-section" aria-labelledby="features-title">
    <div class="landing-container">
      <div class="landing-section-head landing-section-head-center">
        <span class="landing-eyebrow"><i class="bi bi-grid-3x3-gap" aria-hidden="true" /> Features</span>
        <h2 id="features-title" class="landing-heading">
          Todo lo que hace falta <span class="landing-accent">para publicar</span>
        </h2>
        <p class="landing-lead">
          Del video crudo al post publicado: formato, subtítulos, publicación y métricas en el mismo lugar.
        </p>
      </div>

      <div class="landing-features-grid">
        <article v-for="feature in LANDING_FEATURES" :key="feature.title" class="landing-feature-card">
          <span class="landing-feature-chip">{{ feature.chip }}</span>
          <span class="landing-feature-icon" aria-hidden="true"><i class="bi" :class="feature.icon" /></span>
          <h3 class="landing-feature-title">{{ feature.title }}</h3>
          <p class="landing-feature-text">{{ feature.text }}</p>
        </article>
      </div>
    </div>
  </section>
</template>