<template>
  <div class="flex flex-col md:flex-row items-center justify-between gap-4 p-3 bg-[#121824] rounded-xl border border-white/10" style="margin-bottom: 1rem; min-height: 56px">
    <div class="relative flex-1 max-w-md w-full">
      <i class="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" style="font-size: 0.9rem" />
      <input
        :value="q"
        @input="$emit('update:q', ($event.target as HTMLInputElement).value)"
        placeholder="Buscar por título o transcripción..."
        class="w-full pl-9 pr-4 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:border-[#B4F105] transition-colors"
      />
    </div>
    <div class="flex items-center gap-3 w-full md:w-auto justify-end">
      <select :value="minScore" @change="$emit('update:minScore', ($event.target as HTMLSelectElement).value)" class="bg-[#0B0F17] text-xs text-white border border-white/10 rounded-lg px-3 py-2 cursor-pointer focus:outline-none hover:border-white/20 transition-colors">
        <option value="">Todos los scores</option>
        <option value="70">+70 Alto</option>
        <option value="40">+40 Medio</option>
      </select>
      <select :value="sortBy" @change="$emit('update:sortBy', ($event.target as HTMLSelectElement).value)" class="bg-[#0B0F17] text-xs text-white border border-white/10 rounded-lg px-3 py-2 cursor-pointer focus:outline-none hover:border-white/20 transition-colors">
        <option value="created_at_desc">Más recientes</option>
        <option value="created_at_asc">Más antiguos</option>
        <option value="score_desc">Mayor score</option>
        <option value="score_asc">Menor score</option>
      </select>
      <div class="py-1 px-1 bg-[#0B0F17] border border-white/10 rounded-lg flex items-center gap-1">
        <button type="button" @click="$emit('update:viewMode', 'grid')" :class="`px-3 py-1.5 rounded-md text-xs font-bold transition ${viewMode === 'grid' ? 'bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'text-[#94A3B8] hover:text-white'}`" aria-label="Vista de tarjetas">⊞ Grid</button>
        <button type="button" @click="$emit('update:viewMode', 'list')" :class="`px-3 py-1.5 rounded-md text-xs font-bold transition ${viewMode === 'list' ? 'bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'text-[#94A3B8] hover:text-white'}`" aria-label="Vista de tabla">☰ Lista</button>
      </div>
    </div>
  </div>
  <div v-if="hasFilters" class="flex items-center gap-2 mb-3">
    <span class="text-xs font-bold text-[#94A3B8]">Filtros activos</span>
    <button @click="$emit('reset')" class="btn-custom btn-custom-light btn-custom-sm !py-1 !text-xs">Resetear filtros</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  q: string
  minScore: string
  sortBy: string
  viewMode: string
  hasFilters: boolean
}>()
defineEmits<{
  (e: 'update:q', v: string): void
  (e: 'update:minScore', v: string): void
  (e: 'update:sortBy', v: string): void
  (e: 'update:viewMode', v: 'grid' | 'list'): void
  (e: 'reset'): void
}>()
</script>
EOF
echo "FilterBar.vue written ($(wc -l < frontend_vue/src/components/clip-library/FilterBar.vue) lines)"