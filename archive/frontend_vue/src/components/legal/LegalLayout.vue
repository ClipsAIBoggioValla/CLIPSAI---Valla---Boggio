<script setup lang="ts">
defineProps<{
  title: string
  subtitle: string
  icon: string
}>()
</script>

<template>
  <div class="legal-page">
    <div class="legal-container">
      <header class="legal-header">
        <span class="legal-icon" aria-hidden="true"><i class="bi" :class="icon" /></span>
        <h1 class="legal-title">{{ title }}</h1>
        <p class="legal-subtitle">{{ subtitle }}</p>
      </header>
      <div class="legal-content">
        <slot />
      </div>
    </div>
  </div>
</template>