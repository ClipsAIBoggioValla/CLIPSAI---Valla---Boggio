/**
 * Contenido editorial de la landing pública (Issue 32).
 *
 * Un único lugar para el copy de hero, pasos, motor, features y footer.
 * El equivalente Vue vive en frontend_vue/src/components/landing/landingData.ts
 * y se mantiene 1:1 con este archivo (paridad de frontends ~100%).
 */

export const LANDING_SITE_URL = 'https://clipsai.xyz'

export const LANDING_SEO = {
  title: 'ClipsAI — Convertí tus videos en clips virales con IA | 9:16 automático',
  description:
    'ClipsAI analiza el audio de tu video con IA, encuentra los momentos más virales, corta en 9:16 con subtítulos dinámicos y publica en YouTube, Instagram y TikTok. Probalo gratis.',
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
  { href: '#sobre-nosotros', label: 'Sobre nosotros' },
  { href: '#features', label: 'Features' },
]

export interface LandingStat {
  value: string
  label: string
}

export const HERO_STATS: LandingStat[] = [
  { value: '10 clips', label: 'por video, ordenados por score' },
  { value: '30–90 s', label: 'duración Sweet Spot' },
  { value: '1080×1920', label: 'vertical 9:16 quemado' },
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
    title: 'Cargá tu video',
    hint: 'Un mp4 y listo',
    summary:
      'Subís el video y el motor se encarga del resto: valida el archivo, extrae el audio con FFmpeg y arma la cola de trabajo con progreso en vivo.',
    bullets: [
      'Aceptamos mp4, mov y avi; también podés pegar la transcripción si ya la tenés.',
      'POST /videos devuelve 201 y POST /videos/{id}/jobs devuelve 202: el job corre en background.',
      'JobStatus muestra progreso 0 → 100 % con badges PENDING, PROCESSING y COMPLETED.',
    ],
    monitorTitle: 'Ingesta del video',
    rows: [
      { label: 'episodio-42.mp4', meta: '1.24 GB · 1920×1080 · 58 min', badge: 'VIDEO 201', tone: 'slate' },
      { label: 'audio.mp3', meta: 'FFmpeg · -q:a 0 · 44.1 kHz', badge: 'ANALIZADO', tone: 'lime' },
      { label: 'transcripcion.txt', meta: 'faster-whisper · VAD · 612 palabras', badge: 'LISTO', tone: 'lime' },
      { label: 'Job #a1f3 · progreso', meta: 'workers en background', badge: '72 %', tone: 'amber', progress: 72 },
    ],
  },
  {
    id: 'analizar',
    icon: 'bi-cpu',
    title: 'Análisis IA',
    hint: 'Audio + LLM + scoring',
    summary:
      'El audio se mide de verdad y el LLM puntúa cada momento con criterios ponderados. El resultado es un ranking de clips con score de viralidad, título y hook.',
    bullets: [
      'RMS, onsets y KMeans (10 clusters) detectan gritos, silencios y cambios bruscos → top 50 momentos.',
      'LLM con prioridad Anthropic → OpenRouter → OpenAI → DeepSeek, reintentos y fallback determinístico.',
      'Se filtran clips de 30–90 s con score ≥ 5 y se quedan los 10 mejores.',
    ],
    monitorTitle: 'Ranking de viralidad',
    rows: [
      {
        label: 'Clip 3 · 0:42 → 1:28',
        meta: '46 s · hook: "¿Por qué nadie te dice esto?" · revelación',
        badge: '9.1',
        tone: 'lime',
        progress: 91,
      },
      {
        label: 'Clip 7 · 12:05 → 12:47',
        meta: '42 s · criterio: dato + bonus audio > 7',
        badge: '8.4',
        tone: 'lime',
        progress: 84,
      },
      {
        label: 'Clip 1 · 3:10 → 3:51',
        meta: '41 s · criterio: controversia',
        badge: '7.6',
        tone: 'amber',
        progress: 76,
      },
    ],
  },
  {
    id: 'publicar',
    icon: 'bi-send-check',
    title: 'Publicación',
    hint: 'Un clic, tres redes',
    summary:
      'Cada clip se renderiza en vertical con subtítulos quemados y teaser de hook, y después se publica solo en las redes que tengas conectadas por OAuth.',
    bullets: [
      'Corte 9:16 + subtítulos ASS word-level con PlayRes 1080×1920 y teaser de hook de 3 a 6 s.',
      'YouTube Data API, Instagram Graph API y TikTok Content Posting API vía OAuth.',
      'Si el render degrada, el clip se guarda igual con tags["_render_error"] y el job termina COMPLETED.',
    ],
    monitorTitle: 'Estado de publicación',
    rows: [
      { label: 'YouTube Shorts', meta: 'youtube.com/shorts/… · social_post_url guardado', badge: 'PUBLISHED', tone: 'lime' },
      { label: 'Instagram Reels', meta: 'container → poll FINISHED → publish', badge: 'PUBLISHED', tone: 'lime' },
      { label: 'TikTok', meta: 'Content Posting API · FILE_UPLOAD + PKCE', badge: 'PUBLISHED', tone: 'lime' },
      { label: 'Webhook de respaldo', meta: 'PUBLISH_WEBHOOK_URL · red propia', badge: '200 OK', tone: 'slate' },
    ],
  },
]

export interface LandingAboutPillar {
  icon: string
  title: string
  text: string
  code: string
}

/** "Sobre nosotros": motor IA, análisis de audio y scoring de viralidad. */
export const LANDING_ABOUT: LandingAboutPillar[] = [
  {
    icon: 'bi-cpu',
    title: 'Motor IA propio',
    text: 'El pipeline vive en nuestro repositorio, no en una caja negra. engine.py orquesta validación, extracción de audio, armado del prompt, render y validación de clips. Si el proveedor de LLM falla, el fallback determinístico mantiene el job en COMPLETED en lugar de romperlo.',
    code: 'engine.py → procesar_video() · CLIPSAI_PROVEEDOR_LLM=auto',
  },
  {
    icon: 'bi-soundwave',
    title: 'Análisis de audio real',
    text: 'No es decorativo: calculamos la energía RMS frame a frame, detectamos gritos, silencios y cambios bruscos, normalizamos a escala 0–10 y agrupamos con KMeans. De ahí salen los momentos más Intensivos del video, que son los candidatos reales que después puntúa el LLM.',
    code: 'audio_analyzer.py → audio.json + momentos_virales.json (top 50)',
  },
  {
    icon: 'bi-speedometer2',
    title: 'Scoring de viralidad',
    text: 'Seis criterios ponderados —revelación 10, controversia 9, dato 8, emocional 7, técnico 6 y predicción 5— más un bonus cuando la intensidad de audio supera 7. Traducido: no publicás ruido, publicás el material que la audiencia va a mirar hasta el final.',
    code: 'score ≥ 5 · duración 30–90 s · top 10 por score',
  },
]

export const LANDING_STACK = [
  'Python',
  'FFmpeg',
  'faster-whisper',
  'scikit-learn',
  'FastAPI',
  'Express',
  'React',
  'Vue',
  'PostgreSQL',
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
    title: 'Corte vertical 9:16',
    text: '1080×1920 a 30 fps con recorte automático al rostro y loudnorm a −16 LUFS, para que el clip se vea y suene igual en cada red sin que toques un slider.',
    chip: '1080×1920',
  },
  {
    icon: 'bi-badge-cc',
    title: 'Subtítulos dinámicos',
    text: 'ASS word-level quemados sobre el video con PlayRes 1080×1920, estilo por criterio de viralidad y un teaser de hook de 3 a 6 segundos que engancha antes del resto.',
    chip: 'Word-level ASS',
  },
  {
    icon: 'bi-cloud-arrow-up',
    title: 'Autopublicación',
    text: 'OAuth directo a YouTube, Instagram y TikTok. El clip pasa de PUBLISHING a PUBLISHED solo, con el enlace del post guardado en tu biblioteca y un webhook como plan B.',
    chip: 'OAuth 2.0',
  },
  {
    icon: 'bi-speedometer2',
    title: 'Scoring de viralidad',
    text: 'Cada clip vuelve con score 0–10, criterio principal, título sugerido y texto de hook, para que sepas por qué ese fragmento vale más que otro.',
    chip: 'Score 0–10',
  },
  {
    icon: 'bi-collection-play',
    title: 'Biblioteca con búsqueda',
    text: 'Filtros por score mínimo y plataforma, orden por fecha o score, vista en grilla o lista y exportación a CSV o JSON para seguir editando fuera.',
    chip: 'CSV · JSON',
  },
  {
    icon: 'bi-graph-up-arrow',
    title: 'Panel de métricas',
    text: 'KPIs de jobs, clips, horas ahorradas y score promedio, más la distribución por plataforma y la actividad reciente para saber qué contenido rinde.',
    chip: 'KPIs + trends',
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
 * Páginas legales de la plataforma.
 * Los destinos los implementa la Issue 33; el footer ya los publica porque
 * Meta, Google y TikTok las exigen para revisar la app.
 */
export const LANDING_LEGAL_LINKS: LandingFooterLink[] = [
  { label: 'Política de privacidad', href: '/privacy' },
  { label: 'Términos y condiciones', href: '/terms' },
  { label: 'Eliminación de datos', href: '/data-deletion' },
]

/** Etiquetas cortas para la barra inferior del footer. */
export const LANDING_LEGAL_SHORT: LandingFooterLink[] = [
  { label: 'Privacidad', href: '/privacy' },
  { label: 'Términos', href: '/terms' },
  { label: 'Eliminación de datos', href: '/data-deletion' },
]

/** Footer: enlaces legales (Issue 33) + producto. */
export const LANDING_FOOTER_COLUMNS: LandingFooterColumn[] = [
  {
    title: 'Producto',
    links: [
      { label: 'Probar gratis', href: '/auth' },
      { label: 'Panel', href: '/dashboard' },
      { label: 'Biblioteca de clips', href: '/clips' },
      { label: 'Integraciones', href: '/dashboard/integrations' },
    ],
  },
  {
    title: 'Cómo funciona',
    links: [
      { label: 'Cargar video', href: '#como-funciona' },
      { label: 'Análisis IA', href: '#como-funciona' },
      { label: 'Publicación', href: '#como-funciona' },
      { label: 'Features', href: '#features' },
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
export const LANDING_COPYRIGHT = `© ${new Date().getFullYear()} ClipsAI. Motor de viralidad automatizado.`