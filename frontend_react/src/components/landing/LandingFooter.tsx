import { Link } from 'react-router-dom'
import {
  LANDING_CONTACT,
  LANDING_COPYRIGHT,
  LANDING_FOOTER_COLUMNS,
  LANDING_LEGAL_SHORT,
  type LandingFooterLink,
} from './landingData'

function isInternal(href: string): boolean {
  return href.startsWith('/')
}

function FooterLink({ link }: { link: LandingFooterLink }) {
  if (isInternal(link.href)) {
    return (
      <Link to={link.href} className="landing-footer-link">
        {link.label}
      </Link>
    )
  }
  return (
    <a
      href={link.href}
      className="landing-footer-link"
      {...(link.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
    >
      {link.label}
    </a>
  )
}

/** Footer con enlaces a las páginas legales de la plataforma (/privacy, /terms, /data-deletion). */
export default function LandingFooter() {
  return (
    <footer className="landing-footer" aria-labelledby="landing-footer-title">
      <h2 id="landing-footer-title" className="sr-only">
        Pie de página de ClipsAI
      </h2>
      <div className="landing-container">
        <div className="landing-footer-grid">
          <div>
            <span className="landing-brand">
              <i className="bi bi-asterisk" aria-hidden="true" /> clipsai
            </span>
            <p className="landing-footer-about">
              Motor de viralidad automatizado: analizamos el audio de tu video, elegimos los momentos que
              enganchan y los publicamos en vertical. Construido por el equipo de ClipsAI.
            </p>
            <a href={`mailto:${LANDING_CONTACT.email}`} className="landing-footer-link">
              <i className="bi bi-envelope me-2" aria-hidden="true" />
              {LANDING_CONTACT.label}
            </a>
          </div>

          {LANDING_FOOTER_COLUMNS.map((column) => (
            <nav key={column.title} aria-label={column.title}>
              <h3 className="landing-footer-title">{column.title}</h3>
              <ul className="landing-footer-list">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <FooterLink link={link} />
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="landing-footer-bottom">
          <span>{LANDING_COPYRIGHT}</span>
          <div className="landing-footer-legal">
            {LANDING_LEGAL_SHORT.map((link) => (
              <FooterLink key={link.href} link={link} />
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}