import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/auth', name: 'auth', component: () => import('@/views/AuthView.vue') },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { requiresAuth: true } },
    { path: '/clips', name: 'clips', component: () => import('@/views/ClipLibraryView.vue'), meta: { requiresAuth: true } },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { requiresAuth: true } },
    { path: '/upload', name: 'upload', component: () => import('@/views/UploadView.vue'), meta: { requiresAuth: true } },
    { path: '/jobs/:jobId', name: 'job', component: () => import('@/views/JobStatusView.vue'), meta: { requiresAuth: true }, props: true },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated && !auth.isLoading) {
    return '/auth'
  }
  if (to.path === '/auth' && auth.isAuthenticated && !auth.isLoading) {
    return '/upload'
  }
})

export default router
