import { Link } from 'react-router-dom'
import { LANDING_NAV_LINKS } from './landingData'

/** Barra superior de la landing: marca, anclas a secciones reales y CTA a /auth. */
export default function LandingNav() {
  return (
    <header className="landing-nav">
      <div className="landing-container landing-nav-inner">
        <a href="#top" className="landing-brand" aria-label="ClipsAI — volver al inicio">
          <i className="bi bi-asterisk" aria-hidden="true" /> clipsai
        </a>
        <nav className="landing-nav-links" aria-label="Secciones de ClipsAI">
          {LANDING_NAV_LINKS.map((link) => (
            <a key={link.href + link.label} href={link.href} className="landing-nav-link">
              {link.label}
            </a>
          ))}
        </nav>
        <div className="landing-nav-actions">
          <Link to="/auth" className="landing-btn landing-btn-primary">
            Probar gratis
          </Link>
        </div>
      </div>
    </header>
  )
}