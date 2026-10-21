<template>
  <div>
    <div v-if="loading" :class="viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'">
      <div v-for="i in 6" :key="i" class="card-spark animate-pulse">
        <div class="h-4 rounded w-3/4 mb-3 bg-[rgba(255,255,255,0.06)]" />
        <div class="h-3 rounded w-1/2 mb-4 bg-[rgba(255,255,255,0.04)]" />
        <div class="h-10 rounded mb-3 bg-[rgba(255,255,255,0.04)]" />
        <div class="h-3 rounded w-1/3 bg-[rgba(255,255,255,0.04)]" />
      </div>
    </div>

    <div v-else-if="error" role="alert" class="alert-custom alert-custom-danger">
      <i class="bi bi-exclamation-circle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
      <button class="btn-custom btn-custom-danger btn-custom-sm" @click="onFetchClips">Reintentar</button>
    </div>

    <div v-else-if="data && data.items.length === 0" class="card-spark text-center" style="border-style: dashed; padding: 2.5rem; border-color: rgba(180,241,5,0.18)">
      <div class="h-12 w-12 rounded-full flex items-center justify-center text-xl mx-auto bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.06)]">🎬</div>
      <p class="text-sm font-bold mt-4" style="color: #F1F5F9">No hay clips que coincidan</p>
      <p class="text-xs mt-1" style="color: #94A3B8">Prueba ajustando la búsqueda, el filtro de score o el ordenamiento.</p>
      <button v-if="hasFilters" class="btn-custom btn-custom-primary mt-5" @click="onResetFilters">Limpiar filtros</button>
    </div>

    <div v-else-if="data && data.items.length > 0">
      <div v-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <ClipCard
          v-for="clip in data.items" :key="clip.id"
          :clip="clip"
          :rerendering="rerendering"
          :publishing="publishing"
          :sse-publishing="ssePublishing"
          :is-published="clip.status === 'PUBLISHED'"
          :active-publish-id="activePublishId"
          :sse-url="sseUrl"
          :busy="rerendering === clip.id || publishing === clip.id || (ssePublishing && activePublishId === clip.id) || clip.status === 'PUBLISHING'"
          @preview="setPreviewClip"
          @download="handleDownload"
          @toggle="handleToggle"
          @open-publish="openPublish"
        />
      </div>
      <div v-else class="table-card-custom">
        <div class="table-responsive" style="overflow-x: auto">
          <table class="table-custom">
            <thead>
              <tr><th>Título</th><th>Viral Score</th><th>Duración</th><th>ASS / Hook</th><th>Estado</th><th>Acción</th></tr>
            </thead>
            <tbody>
              <tr v-for="clip in data.items" :key="clip.id" :class="rerendering === clip.id ? 'opacity-60' : ''">
                <td>
                  <p class="font-bold line-clamp-1 cursor-pointer hover:text-[#B4F105]" style="color: var(--text-main)" @click="setPreviewClip(clip)">{{ clip.title || 'Sin título' }}</p>
                  <p v-if="clip.transcript" class="text-xs line-clamp-1 mt-1" style="color: var(--text-muted-green)">{{ clip.transcript }}</p>
                </td>
                <td><span :class="scoreBadge(clip.score)">Viral Score: {{ formatScore(clip.score) }}/100</span></td>
                <td class="font-mono text-xs" style="color: var(--text-muted-green)">{{ formatDuration(clip) }}<br /><span class="text-[11px] text-[#64748B]">{{ formatTimeRange(clip) }}</span></td>
                <td>
                  <div class="flex items-center gap-2">
                    <label class="flex items-center gap-1 text-[11px]"><input type="checkbox" :checked="!!clip.has_ass" :disabled="rerendering === clip.id || publishing === clip.id || (ssePublishing && activePublishId === clip.id)" @change="handleToggle(clip, ($event.target as HTMLInputElement).checked, !!clip.has_hook)" class="accent-[#B4F105] disabled:opacity-50" /> ASS</label>
                    <label class="flex items-center gap-1 text-[11px]"><input type="checkbox" :checked="!!clip.has_hook" :disabled="rerendering === clip.id || publishing === clip.id || (ssePublishing && activePublishId === clip.id)" @change="handleToggle(clip, !!clip.has_ass, ($event.target as HTMLInputElement).checked)" class="accent-[#B4F105] disabled:opacity-50" /> Hook</label>
                    <span v-if="rerendering === clip.id" class="h-3 w-3 animate-spin rounded-full border border-white/30 border-t-[#B4F105]" />
                  </div>
                </td>
                <td>
                  <span v-if="publishing === clip.id || (ssePublishing && activePublishId === clip.id)" class="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse">Publicando...</span>
                  <span v-else-if="clip.status === 'PUBLISHED'" class="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span>
                  <span v-else-if="publishBadge(clip.status)" class="inline-flex px-2 py-1 rounded-full text-[11px] font-bold border" :class="publishBadge(clip.status)!.cls">{{ publishBadge(clip.status)!.label }}</span>
                  <span v-else class="text-xs text-[#94A3B8]">ready</span>
                  <a v-if="clip.social_post_url || ((clip.status === 'PUBLISHED') && sseUrl && activePublishId === clip.id)" :href="clip.social_post_url || sseUrl || '#'" target="_blank" rel="noopener noreferrer" class="ml-2 text-xs text-[#B4F105] hover:underline">Ver</a>
                </td>
                <td>
                  <div class="flex items-center gap-1">
                    <button type="button" class="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Vista previa 9:16" @click="setPreviewClip(clip)"><i class="bi bi-eye" /></button>
                    <button type="button" class="btn-custom btn-custom-light btn-custom-sm !text-xs" title="Descargar MP4" @click="handleDownload(clip)"><i class="bi bi-download" /></button>
                    <button type="button" @click="openPublish(clip)" :disabled="rerendering === clip.id || publishing === clip.id || (ssePublishing && activePublishId === clip.id)" class="btn-custom btn-custom-primary btn-custom-sm !text-xs disabled:opacity-50">{{ publishing === clip.id || (ssePublishing && activePublishId === clip.id) ? 'Publicando...' : (clip.status === 'PUBLISHED' ? 'Publicado ✅' : 'Publicar') }}</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="table-footer-control" style="border-radius: var(--radius-xl); margin-top: 1rem">
        <span class="table-pagination-info">Mostrando <strong style="color: var(--text-main)">{{ data!.items.length }}</strong> de <strong style="color: var(--text-main)">{{ data!.total }}</strong> clips · Página {{ data!.page }} de {{ data!.total_pages || 1 }}</span>
        <div class="flex items-center gap-2">
          <button :disabled="page <= 1" class="btn-custom btn-custom-light btn-custom-sm" @click="$emit('setPage', Math.max(1, page - 1))">Anterior</button>
          <span class="table-pagination-info px-2">Página {{ page }} de {{ totalPages || 1 }}</span>
          <button :disabled="page >= totalPages" class="btn-custom btn-custom-primary btn-custom-sm" @click="$emit('setPage', Math.min(totalPages || 1, page + 1))">Siguiente</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ClipListItem, ClipListResponse } from '@/types/api'
import { formatScore, formatDuration, formatTimeRange, scoreBadge, publishBadge } from './helpers'
import ClipCard from './ClipCard.vue'

defineProps<{
  data: ClipListResponse | null
  loading: boolean
  error: string | null
  viewMode: string
  hasFilters: boolean
  page: number
  totalPages: number
  rerendering: string | null
  publishing: string | null
  ssePublishing: boolean
  activePublishId: string | null
  sseUrl: string | null
  setPreviewClip: (c: ClipListItem) => void
  handleDownload: (c: ClipListItem) => void
  handleToggle: (c: ClipListItem, ass: boolean, hook: boolean) => void
  openPublish: (c: ClipListItem) => void
}>()
defineEmits<{
  (e: 'fetchClips'): void
  (e: 'resetFilters'): void
  (e: 'setPage', p: number): void
}>()
</script>
EOF
echo "rewrote ClipResults.vue ($(wc -l < frontend_vue/src/components/clip-library/ClipResults.vue) lines)"