import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/auth' },
    { path: '/auth', name: 'auth', component: () => import('@/views/AuthView.vue') },
    { path: '/upload', name: 'upload', component: () => import('@/views/UploadView.vue'), meta: { requiresAuth: true } },
    { path: '/jobs/:jobId', name: 'job', component: () => import('@/views/JobStatusView.vue'), meta: { requiresAuth: true }, props: true },
    { path: '/:pathMatch(.*)*', redirect: '/auth' },
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
