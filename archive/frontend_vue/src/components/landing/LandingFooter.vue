<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { LANDING_CONTACT, LANDING_COPYRIGHT, LANDING_FOOTER_COLUMNS, LANDING_LEGAL_SHORT } from './landingData'

function isInternal(href: string): boolean {
  return href.startsWith('/')
}
</script>

<template>
  <footer class="landing-footer" aria-labelledby="landing-footer-title">
    <h2 id="landing-footer-title" class="sr-only">Pie de página de ClipsAI</h2>
    <div class="landing-container">
      <div class="landing-footer-grid">
        <div>
          <span class="landing-brand"><i class="bi bi-asterisk" aria-hidden="true" /> clipsai</span>
          <p class="landing-footer-about">
            Motor de viralidad automatizado: analizamos el audio de tu video, elegimos los momentos que enganchan
            y los publicamos en vertical. Construido por el equipo de ClipsAI.
          </p>
          <a :href="`mailto:${LANDING_CONTACT.email}`" class="landing-footer-link">
            <i class="bi bi-envelope me-2" aria-hidden="true" />
            {{ LANDING_CONTACT.label }}
          </a>
        </div>

        <nav v-for="column in LANDING_FOOTER_COLUMNS" :key="column.title" :aria-label="column.title">
          <h3 class="landing-footer-title">{{ column.title }}</h3>
          <ul class="landing-footer-list">
            <li v-for="link in column.links" :key="link.label">
              <RouterLink v-if="isInternal(link.href)" :to="link.href" class="landing-footer-link">
                {{ link.label }}
              </RouterLink>
              <a
                v-else
                :href="link.href"
                class="landing-footer-link"
                :target="link.external ? '_blank' : undefined"
                :rel="link.external ? 'noopener noreferrer' : undefined"
              >
                {{ link.label }}
              </a>
            </li>
          </ul>
        </nav>
      </div>

      <div class="landing-footer-bottom">
        <span>{{ LANDING_COPYRIGHT }}</span>
        <div class="landing-footer-legal">
          <RouterLink v-for="link in LANDING_LEGAL_SHORT" :key="link.href" :to="link.href" class="landing-footer-link">
            {{ link.label }}
          </RouterLink>
        </div>
      </div>
    </div>
  </footer>
</template>