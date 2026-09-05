<script setup lang="ts">
import { computed, ref } from 'vue'
const props = withDefaults(defineProps<{ name?: string | null; email?: string | null; avatarUrl?: string | null; size?: number }>(), { size: 32 })
const imgError = ref(false)

function getInitials(name?: string | null, email?: string | null): string {
  const src = (name && name.trim()) ? name.trim() : (email ?? '')
  if (!src) return 'U'
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/).filter(Boolean)
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return parts[0].slice(0, 2).toUpperCase()
  }
  return src.slice(0, 2).toUpperCase()
}
const initials = computed(() => getInitials(props.name, props.email))
const style = computed(() => ({ width: `${props.size}px`, height: `${props.size}px`, fontSize: `${props.size! * 0.38}px` }))
const hasAvatar = computed(() => typeof props.avatarUrl === 'string' && props.avatarUrl.trim() !== '' && /^https?:\/\//.test(props.avatarUrl.trim()) && !imgError.value)
</script>

<template>
  <img v-if="hasAvatar" :src="props.avatarUrl!.trim()" :alt="props.name ?? props.email ?? 'avatar'" class="rounded-full object-cover shrink-0" :style="{ width: `${props.size}px`, height: `${props.size}px` }" @error="imgError = true" />
  <span v-else class="inline-flex items-center justify-center rounded-full font-extrabold shrink-0 bg-gradient-to-tr from-emerald-500 to-[#B4F105] text-[#080C14] shadow-[0_0_16px_rgba(180,241,5,0.35)]" :style="{ ...style, border: '1px solid rgba(180,241,5,0.3)' }" :aria-label="props.name ?? props.email ?? 'avatar'">{{ initials }}</span>
</template>
