<script setup lang="ts">
import { computed, ref } from 'vue'
import { LANDING_STEPS } from './landingData'

/** "Cómo funciona": 3 pasos (cargar video → análisis IA → publicación) navegables con mouse y teclado. */
const active = ref(0)
const tabs = ref<Array<HTMLButtonElement | null>>([])
const step = computed(() => LANDING_STEPS[active.value])

function select(index: number) {
  active.value = index
}

function onKeydown(event: KeyboardEvent, index: number) {
  const last = LANDING_STEPS.length - 1
  let next: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = index === last ? 0 : index + 1
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = index === 0 ? last : index - 1
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = last
  if (next === null) return
  event.preventDefault()
  active.value = next
  tabs.value[next]?.focus()
}
</script>

<template>
  <section id="como-funciona" class="landing-section" aria-labelledby="como-funciona-title">
    <div class="landing-container">
      <div class="landing-section-head landing-section-head-center">
        <span class="landing-eyebrow"><i class="bi bi-signpost-split" aria-hidden="true" /> Cómo funciona</span>
        <h2 id="como-funciona-title" class="landing-heading">
          Tres pasos, <span class="landing-accent">un solo trabajo pendiente</span>
        </h2>
        <p class="landing-lead">
          El mismo pipeline que corre en producción, paso a paso. Elegí un paso para ver qué pasa por debajo.
        </p>
      </div>

      <div class="landing-steps">
        <div class="landing-step-list" role="tablist" aria-label="Pasos de ClipsAI" aria-orientation="vertical">
          <button
            v-for="(item, index) in LANDING_STEPS"
            :id="`step-tab-${item.id}`"
            :key="item.id"
            :ref="(el) => (tabs[index] = el as HTMLButtonElement)"
            type="button"
            role="tab"
            class="landing-step-tab"
            :aria-selected="index === active"
            :aria-controls="`step-panel-${item.id}`"
            :tabindex="index === active ? 0 : -1"
            @click="select(index)"
            @keydown="onKeydown($event, index)"
          >
            <span class="landing-step-index" aria-hidden="true">{{ index + 1 }}</span>
            <span>
              <span class="landing-step-tab-title">{{ item.title }}</span>
              <span class="landing-step-tab-hint">{{ item.hint }}</span>
            </span>
          </button>
        </div>

        <div
          :id="`step-panel-${step.id}`"
          role="tabpanel"
          :aria-labelledby="`step-tab-${step.id}`"
          tabindex="0"
          class="landing-panel"
        >
          <h3 class="landing-panel-title">
            <i class="bi me-2 text-[#B4F105]" :class="step.icon" aria-hidden="true" />
            {{ step.title }}
          </h3>
          <p class="landing-panel-text">{{ step.summary }}</p>
          <ul class="landing-panel-list">
            <li v-for="bullet in step.bullets" :key="bullet">
              <i class="bi bi-check-circle-fill" aria-hidden="true" />
              <span>{{ bullet }}</span>
            </li>
          </ul>

          <div class="landing-monitor" aria-hidden="true">
            <p class="landing-monitor-head"><i class="bi" :class="step.icon" /> {{ step.monitorTitle }}</p>
            <div class="landing-monitor-rows">
              <div v-for="row in step.rows" :key="row.label" class="landing-monitor-row">
                <div class="landing-monitor-row-top">
                  <span class="landing-monitor-row-label">{{ row.label }}</span>
                  <span class="landing-monitor-badge" :class="row.tone">{{ row.badge }}</span>
                </div>
                <span class="landing-monitor-row-meta">{{ row.meta }}</span>
                <span v-if="row.progress !== undefined" class="landing-monitor-bar">
                  <span :style="{ width: `${row.progress}%` }" />
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>