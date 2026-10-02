import { LANDING_SEO, LANDING_SITE_URL } from './landingData'

function upsertMeta(selector: string, attr: 'name' | 'property', key: string, content: string) {
  let tag = document.head.querySelector<HTMLMetaElement>(selector)
  if (!tag) {
    tag = document.createElement('meta')
    tag.setAttribute(attr, key)
    document.head.appendChild(tag)
  }
  tag.setAttribute('content', content)
}

/**
 * Sincroniza el head con los datos de la landing.
 * El index.html ya trae los tags para crawlers que no ejecutan JS; esto mantiene
 * la coherencia cuando el usuario navega dentro del SPA hacia `/`.
 */
export function applyLandingSeo() {
  if (typeof document === 'undefined') return
  document.title = LANDING_SEO.title

  upsertMeta('meta[name="description"]', 'name', 'description', LANDING_SEO.description)
  upsertMeta('meta[property="og:title"]', 'property', 'og:title', LANDING_SEO.title)
  upsertMeta('meta[property="og:description"]', 'property', 'og:description', LANDING_SEO.description)
  upsertMeta('meta[property="og:url"]', 'property', 'og:url', `${LANDING_SITE_URL}/`)
  upsertMeta('meta[name="twitter:title"]', 'name', 'twitter:title', LANDING_SEO.title)
  upsertMeta('meta[name="twitter:description"]', 'name', 'twitter:description', LANDING_SEO.description)

  let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!canonical) {
    canonical = document.createElement('link')
    canonical.rel = 'canonical'
    document.head.appendChild(canonical)
  }
  canonical.href = `${LANDING_SITE_URL}/`
}