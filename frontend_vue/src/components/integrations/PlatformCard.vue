<template>
  <div class="card-spark">
    <div class="flex items-center gap-3 mb-3">
      <span class="h-10 w-10 rounded-xl flex items-center justify-center text-xl" :class="iconWrapClass"><i :class="icon" /></span>
      <div>
        <h3 class="font-bold text-white">{{ name }}</h3>
        <p v-if="connected && username" class="text-xs font-mono text-emerald-300">@{{ username }}</p>
        <p v-else class="text-xs text-[#94A3B8]">{{ description }}</p>
      </div>
      <span v-if="connected" class="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20"><span class="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado</span>
      <span v-else class="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-white/5 text-[#94A3B8] border border-white/10">No conectado</span>
    </div>
    <p class="text-sm text-[#94A3B8] mb-4">{{ descriptionLong }}</p>
    <slot />
    <p class="text-xs text-[#64748B] mt-2 text-center">{{ endpointHint }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  name: string
  icon: string
  iconWrapClass: string
  connected: boolean
  username: string | null
  description: string
  descriptionLong: string
  endpointHint: string
}>()
</script>
