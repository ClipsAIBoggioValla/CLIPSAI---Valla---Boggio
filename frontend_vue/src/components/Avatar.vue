<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ name?: string | null; email?: string | null; size?: number }>(), { size: 32 })

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
function hashColor(str: string): string {
  const colors = ['bg-violet-600', 'bg-indigo-600', 'bg-emerald-600', 'bg-sky-600', 'bg-amber-600', 'bg-rose-600', 'bg-teal-600', 'bg-fuchsia-600']
  let h = 0
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0
  return colors[h % colors.length]
}
const initials = computed(() => getInitials(props.name, props.email))
const bg = computed(() => hashColor((props.name ?? props.email ?? 'user')))
const style = computed(() => ({ width: `${props.size}px`, height: `${props.size}px`, fontSize: `${props.size! * 0.38}px` }))
</script>

<template>
  <span :class="['inline-flex items-center justify-center rounded-full text-white font-bold shrink-0', bg]" :style="style" :aria-label="name ?? email ?? 'avatar'">{{ initials }}</span>
</template>
