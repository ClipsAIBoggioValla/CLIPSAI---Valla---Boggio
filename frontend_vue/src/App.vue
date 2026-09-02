/* WCAG AAA coverage: text-slate-950 dark:text-white font-bold | text-slate-900 dark:text-slate-100 font-medium | text-slate-700 dark:text-slate-300 | bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 | bg-white dark:bg-slate-800 text-slate-950 dark:text-white font-semibold border-2 border-slate-300 dark:border-slate-700 focus:border-violet-600 focus:ring-2 focus:ring-violet-600/20 placeholder-slate-500 dark:placeholder-slate-400 | bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 min-h-screen | bg-white dark:bg-slate-900 border-b-2 border-slate-200 dark:border-slate-800 | bg-slate-200/80 dark:bg-slate-800 text-slate-950 dark:text-slate-200 font-bold border-b-2 border-slate-300 */
<script setup lang="ts">
import Navbar from '@/components/Navbar.vue'
</script>

<template>
  <div class="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
    <Navbar />
    <RouterView />
  </div>
</template>
