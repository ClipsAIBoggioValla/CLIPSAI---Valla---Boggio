import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Landing pública (Issue 32): anteportada sin auth para usuarios anónimos
    // y revisores de las APIs de redes sociales. Con sesión activa, LandingView
    // redirige a /dashboard.
    { path: '/', name: 'landing', component: () => import('@/views/LandingView.vue'), meta: { public: true } },
    // Páginas legales (Issue 33): públicas, requeridas por Meta/Google/TikTok
    { path: '/politica-de-privacidad', name: 'privacy', component: () => import('@/views/legal/PrivacyView.vue'), meta: { public: true } },
    { path: '/terminos-y-condiciones', name: 'terms', component: () => import('@/views/legal/TermsView.vue'), meta: { public: true } },
    { path: '/eliminacion-de-datos', name: 'data-deletion', component: () => import('@/views/legal/DataDeletionView.vue'), meta: { public: true } },
    { path: '/auth', name: 'auth', component: () => import('@/views/AuthView.vue') },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { requiresAuth: true } },
    { path: '/clips', name: 'clips', component: () => import('@/views/ClipLibraryView.vue'), meta: { requiresAuth: true } },
    { path: '/library', name: 'library', component: () => import('@/views/LibraryView.vue'), meta: { requiresAuth: true } },
    { path: '/upload', name: 'upload', component: () => import('@/views/UploadView.vue'), meta: { requiresAuth: true } },
    { path: '/jobs/:jobId', name: 'job', component: () => import('@/views/JobStatusView.vue'), meta: { requiresAuth: true }, props: true },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { requiresAuth: true } },
    { path: '/dashboard/integrations', name: 'integrations', component: () => import('@/views/IntegrationsView.vue'), meta: { requiresAuth: true } },
    { path: '/integrations', redirect: '/dashboard/integrations' },
    { path: '/404', name: 'notfound', component: () => import('@/views/NotFoundView.vue') },
    { path: '/login', redirect: '/auth' },
    { path: '/:pathMatch(.*)*', redirect: '/404' },
  ],
})

const ALLOW_ANONYMOUS =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_ALLOW_ANONYMOUS) === 'true'

router.beforeEach((to) => {
  const auth = useAuthStore()
  let hasToken = false
  try {
    hasToken = !!localStorage.getItem('clipsai_token') || !!localStorage.getItem('token') || !!localStorage.getItem('access_token')
  } catch {
    hasToken = !!auth.token
  }
  // Modo local/abierto o fallback cuando backend no responde: no bloquear vistas principales como /upload o /dashboard
  // Garantiza contenido visible en lugar de pantalla vacía.
  // `/` (landing pública, Issue 32) no entra acá a propósito: se renderiza siempre
  // sin auth para que los revisores de Meta/Google/TikTok puedan verla.
  if (to.path === '/upload' || to.path === '/dashboard') {
    if (ALLOW_ANONYMOUS) return
    // Fallback: si no hay token pero es vista principal, permitir renderizado dentro de Layout con UploadPage/dashboard
    // en lugar de redirigir a ruta no definida o retornar null
    if (!hasToken && !auth.isLoading) {
      // Permitir acceso anónimo a vistas principales para evitar bloqueo
      return
    }
    if (to.meta.requiresAuth && !hasToken && auth.isLoading) {
      // Esperar rescate 1000ms
      return
    }
  }
  if (to.meta.requiresAuth && !hasToken) {
    // Si isLoading aún true, esperar al timeout de rescate (1000ms) en lugar de bloquear con spinner infinito
    if (auth.isLoading) return
    return '/login'
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated && !auth.isLoading && !hasToken) {
    return '/login'
  }
  if ((to.path === '/auth' || to.path === '/login') && auth.isAuthenticated && !auth.isLoading) {
    return '/upload'
  }
  if ((to.path === '/auth' || to.path === '/login') && hasToken && auth.isAuthenticated) {
    return '/upload'
  }
})

export default router
