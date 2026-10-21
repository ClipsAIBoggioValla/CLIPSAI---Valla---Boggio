<template>
  <div class="max-w-6xl mx-auto">
    <div v-if="toast" class="fixed top-4 right-4 z-[9999] bg-[#121824] border border-[#B4F105]/30 text-[#F1F5F9] px-4 py-3 rounded-xl shadow-xl text-sm font-semibold">{{ toast }}</div>
    <div class="page-header" style="margin-bottom: 2rem">
      <div>
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]"><i class="bi bi-collection-play" style="font-size: 1.15rem" /></span>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]"><i class="bi bi-stars" /> Biblioteca</span>
          <span v-if="data" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border bg-[rgba(180,241,5,0.10)] text-[#B4F105] border-[rgba(180,241,5,0.22)]">{{ data.total }} clips</span>
          <span v-if="routeJobId" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-[#0B0F17] text-[#94A3B8] border border-white/10">job {{ routeJobId.slice(0,8) }}…</span>
        </div>
        <h1 class="page-title" style="margin-bottom: 0; font-size: 2.25rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; color: #F1F5F9">Biblioteca de Clips</h1>
        <p class="page-subtitle" style="margin-bottom: 0; margin-top: 0.7rem; font-size: 0.92rem; font-weight: 500; color: #94A3B8; line-height: 1.6; max-width: 640px">Explora, busca y gestiona todos tus clips generados con filtros inteligentes y paginación fluida.</p>
      </div>
    </div>

    <FilterBar
      :q="q" :min-score="minScore" :sort-by="sortBy" :view-mode="viewMode" :has-filters="hasFilters()"
      @update:q="q = $event" @update:min-score="minScore = $event" @update:sort-by="sortBy = $event as ClipSortBy"
      @update:view-mode="viewMode = $event" @reset="resetFilters"
    />

    <ClipResults
      :data="data" :loading="loading" :error="error" :view-mode="viewMode" :has-filters="hasFilters()"
      :page="page" :total-pages="data?.total_pages ?? 0" :rerendering="rerendering" :publishing="publishing"
      :sse-publishing="ssePublishing" :active-publish-id="activePublishId" :sse-url="sseUrl"
      :set-preview-clip="(c) => (previewClip = c)" :handle-download="handleDownload" :handle-toggle="handleToggle" :open-publish="openPublish"
      @fetch-clips="fetchClips" @reset-filters="resetFilters" @set-page="page = $event"
      @download="handleDownload" @toggle="handleToggle" @open-publish="openPublish"
    />

    <PreviewModal
      v-if="previewClip" :clip="previewClip" :sse-url="sseUrl" :active-publish-id="activePublishId" :api-base-url="API_BASE_URL"
      @close="previewClip = null" @download="handleDownload" @open-publish="(c) => { previewClip = null; openPublish(c) }" :get-video-src="getVideoSrc"
    />

    <PublishDialog
      v-if="publishClip" :clip="publishClip" :platform="platform" :caption="caption" :webhook-url="webhookUrl"
      :publishing="publishing" :is-published="publishClip.status === 'PUBLISHED'" :sse-publishing="ssePublishing" :active-publish-id="activePublishId"
      @close="publishClip = null" @submit="submitPublish"
      @update:platform="platform = $event" @update:caption="caption = $event" @update:webhook-url="webhookUrl = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { useClipLibrary } from '@/composables/useClipLibrary'
import FilterBar from '@/components/clip-library/FilterBar.vue'
import ClipResults from '@/components/clip-library/ClipResults.vue'
import PreviewModal from '@/components/clip-library/PreviewModal.vue'
import PublishDialog from '@/components/clip-library/PublishDialog.vue'
import type { ClipSortBy } from '@/types/api'

const {
  route, routeJobId, q, debouncedQ, minScore, sortBy, page, limit, viewMode,
  data, loading, error, publishClip, platform, caption, webhookUrl, publishing,
  toast, rerendering, previewClip, activePublishId, sseStatus, sseUrl, ssePublishing,
  routeQ, RAW, API_BASE_URL, getVideoSrc, hasFilters, fetchClips, resetFilters,
  openPublish, submitPublish, handleToggle, handleDownload,
} = useClipLibrary()

</script>
