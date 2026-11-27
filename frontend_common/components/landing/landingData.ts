/**
 * Contenido editorial de la landing pública (Issue 32).
 *
 * Un único lugar para los textos de la landing y el footer.
 * Consumido por frontend_react vía shim (single source of truth).
 * El frontend Vue legacy se archivó en archive/frontend_vue/ (Issue #110).
 */

export const LANDING_SITE_URL = 'https://clipsai.xyz'

export const LANDING_SEO = {
  title: 'ClipsAI — Publicá más, editá menos',
  description:
    'Convertí tus videos en clips verticales con subtítulos y compartilos en YouTube, Instagram y TikTok. Probá ClipsAI gratis.',
  locale: 'es_AR',
  ogImage: `${LANDING_SITE_URL}/og-clipsai.png`,
} as const

export interface LandingNavLink {
  href: string
  label: string
}

/** Enlaces internos (anclas reales: Lighthouse "crawlable anchors" los exige con destino). */
export const LANDING_NAV_LINKS: LandingNavLink[] = [
  { href: '#como-funciona', label: 'Cómo funciona' },
  { href: '#sobre-nosotros', label: 'Beneficios' },
  { href: '#features', label: 'Funciones' },
]

export interface LandingStat {
  value: string
  label: string
}

export const HERO_STATS: LandingStat[] = [
  { value: 'Los mejores clips', label: 'según la duración de tu video' },
  { value: '30–90 s', label: 'momentos que enganchan' },
  { value: 'Vertical 9:16', label: 'listo para publicar' },
  { value: '3 redes', label: 'YouTube · Instagram · TikTok' },
]

/** Filas del mock visual de cada paso (panel interactivo de "Cómo funciona"). */
export interface LandingMonitorRow {
  label: string
  meta: string
  badge: string
  tone: 'lime' | 'amber' | 'slate'
  progress?: number
}

export interface LandingStep {
  id: string
  icon: string
  title: string
  hint: string
  summary: string
  bullets: string[]
  monitorTitle: string
  rows: LandingMonitorRow[]
}

export const LANDING_STEPS: LandingStep[] = [
  {
    id: 'cargar',
    icon: 'bi-cloud-arrow-up',
    title: 'Subís tu video',
    hint: 'Un clic y arrancamos',
    summary: 'Subilo una vez. Nosotros hacemos el resto.',
    bullets: ['Elegí tu video y empezá.', 'Seguí el progreso mientras preparamos tus clips.'],
    monitorTitle: 'Tu video',
    rows: [
      { label: 'Video listo', meta: 'Ya podés crear tus clips', badge: 'Listo', tone: 'lime' },
      { label: 'Un clic', meta: 'Y nos ponemos en marcha', badge: 'Fácil', tone: 'slate' },
    ],
  },
  {
    id: 'analizar',
    icon: 'bi-cpu',
    title: 'Elegimos lo mejor',
    hint: 'Momentos que enganchan',
    summary: 'Encontramos los momentos que tu audiencia va a querer ver.',
    bullets: ['Detectamos los mejores fragmentos.', 'Encontrá lo mejor de cada grabación.'],
    monitorTitle: 'Tus mejores momentos',
    rows: [
      {
        label: 'Clip destacado',
        meta: 'Un momento que atrapa desde el inicio',
        badge: '9.1',
        tone: 'lime',
        progress: 91,
      },
      {
        label: 'Clip para compartir',
        meta: 'Una idea que vale la pena compartir',
        badge: '8.4',
        tone: 'lime',
        progress: 84,
      },
      {
        label: 'Otro gran momento',
        meta: 'Más contenido listo para publicar',
        badge: '7.6',
        tone: 'amber',
        progress: 76,
      },
    ],
  },
  {
    id: 'publicar',
    icon: 'bi-send-check',
    title: 'Se publica solo',
    hint: 'En tus redes, sin esfuerzo',
    summary: 'Clips verticales con subtítulos, listos para tus redes.',
    bullets: ['Subtítulos y gancho inicial incluidos.', 'Compartí en YouTube, Instagram y TikTok.'],
    monitorTitle: 'Tus redes',
    rows: [
      { label: 'YouTube Shorts', meta: 'Tu clip está listo para compartir', badge: 'Listo', tone: 'lime' },
      { label: 'Instagram Reels', meta: 'Tu clip está listo para compartir', badge: 'Listo', tone: 'lime' },
      { label: 'TikTok', meta: 'Tu clip está listo para compartir', badge: 'Listo', tone: 'lime' },
    ],
  },
]

export interface LandingAboutPillar {
  icon: string
  title: string
  text: string
}

/** Beneficios que hacen más fácil compartir videos. */
export const LANDING_ABOUT: LandingAboutPillar[] = [
  {
    icon: 'bi-stars',
    title: 'Detección automática',
    text: 'Encontramos los momentos que vale la pena compartir.',
  },
  {
    icon: 'bi-soundwave',
    title: 'Ritmo y voz',
    text: 'Cada clip conserva la energía y tu forma de contar.',
  },
  {
    icon: 'bi-speedometer2',
    title: 'Puntaje de clips',
    text: 'Encontrá tus favoritos y elegí qué publicar primero.',
  },
]

export interface LandingFeature {
  icon: string
  title: string
  text: string
  chip: string
}

/** Features grid. Las tres primeras son los destacados que pide la issue. */
export const LANDING_FEATURES: LandingFeature[] = [
  {
    icon: 'bi-aspect-ratio',
    title: 'Formato vertical',
    text: 'Tus videos, listos para verse en el celular.',
    chip: '9:16',
  },
  {
    icon: 'bi-badge-cc',
    title: 'Subtítulos animados',
    text: 'Fáciles de seguir y sincronizados con cada palabra.',
    chip: 'Listos para ver',
  },
  {
    icon: 'bi-cloud-arrow-up',
    title: 'Publicación automática',
    text: 'Compartí tus clips en tus redes sin subirlos uno por uno.',
    chip: '3 redes',
  },
  {
    icon: 'bi-speedometer2',
    title: 'Puntaje de clips',
    text: 'Descubrí de un vistazo qué momentos destacan.',
    chip: 'Elegí tus favoritos',
  },
  {
    icon: 'bi-collection-play',
    title: 'Tu biblioteca',
    text: 'Todos tus clips, ordenados y listos para volver a compartir.',
    chip: 'Todo en un lugar',
  },
  {
    icon: 'bi-graph-up-arrow',
    title: 'Métricas claras',
    text: 'Mirá cómo crece tu contenido y qué clips funcionan mejor.',
    chip: 'Tu progreso',
  },
]

export interface LandingFooterLink {
  label: string
  href: string
  external?: boolean
}

export interface LandingFooterColumn {
  title: string
  links: LandingFooterLink[]
}

/**
 * Páginas legales de la plataforma (Issue 33).
 * Meta, Google y TikTok las exigen para revisar la app.
 */
export const LANDING_LEGAL_LINKS: LandingFooterLink[] = [
  { label: 'Política de privacidad', href: '/politica-de-privacidad' },
  { label: 'Términos y condiciones', href: '/terminos-y-condiciones' },
  { label: 'Eliminación de datos', href: '/eliminacion-de-datos' },
]

/** Etiquetas cortas para la barra inferior del footer. */
export const LANDING_LEGAL_SHORT: LandingFooterLink[] = [
  { label: 'Privacidad', href: '/politica-de-privacidad' },
  { label: 'Términos', href: '/terminos-y-condiciones' },
  { label: 'Eliminación de datos', href: '/eliminacion-de-datos' },
]

/** Footer: enlaces legales (Issue 33) + producto. */
export const LANDING_FOOTER_COLUMNS: LandingFooterColumn[] = [
  {
    title: 'Producto',
    links: [
      { label: 'Probar gratis', href: '/auth' },
      { label: 'Panel', href: '/dashboard' },
      { label: 'Biblioteca de clips', href: '/clips' },
      { label: 'Conectá tus redes', href: '/dashboard/integrations' },
    ],
  },
  {
    title: 'Cómo funciona',
    links: [
      { label: 'Subí tu video', href: '#como-funciona' },
      { label: 'Elegimos lo mejor', href: '#como-funciona' },
      { label: 'Se publica solo', href: '#como-funciona' },
      { label: 'Funciones', href: '#features' },
    ],
  },
  {
    title: 'Legal',
    links: LANDING_LEGAL_LINKS,
  },
]

export const LANDING_CONTACT = {
  email: 'hola@clipsai.xyz',
  label: 'hola@clipsai.xyz',
}

/** Etiqueta de copyright del footer. */
export const LANDING_COPYRIGHT = `© ${new Date().getFullYear()} ClipsAI. Publicá más, editá menos.`
