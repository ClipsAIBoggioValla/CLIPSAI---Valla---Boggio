import { Link } from 'react-router-dom'
import { HERO_STATS } from './landingData'

const WAVE_BARS = Array.from({ length: 26 }, (_, i) => i)

const PREVIEW_STEPS = [
  { icon: 'bi-soundwave', label: 'Mejores momentos' },
  { icon: 'bi-stars', label: '10 clips destacados' },
  { icon: 'bi-phone', label: 'Vertical y subtitulado' },
  { icon: 'bi-send-check', label: 'Listo para tus redes' },
]

/** Hero: titular de impacto, propuesta de valor y CTA "Probar gratis" → /auth. */
export default function LandingHero() {
  return (
    <section className="landing-hero" aria-labelledby="hero-title">
      <div className="landing-container landing-hero-grid">
        <div>
          <span className="landing-eyebrow">
            <i className="bi bi-stars" aria-hidden="true" /> Subí un video. Publicá en todos lados.
          </span>
          <h1 id="hero-title" className="landing-heading">
            Tus videos largos, <span className="landing-accent">listos para viralizarse solos.</span>
          </h1>
          <p className="landing-lead">
            Detectamos los mejores momentos, los pasamos a vertical con subtítulos y los publicamos en YouTube,
            Instagram y TikTok.
          </p>
          <div className="landing-cta-row">
            <Link to="/auth" className="landing-btn landing-btn-primary">
              Probar gratis <i className="bi bi-arrow-right" aria-hidden="true" />
            </Link>
            <a href="#como-funciona" className="landing-btn landing-btn-ghost">
              <i className="bi bi-play-circle" aria-hidden="true" /> Ver cómo funciona
            </a>
          </div>
          <p className="landing-cta-note">
            Sin tarjeta · Listo en minutos · Todo en un clic
          </p>
        </div>

        <div className="landing-hero-visual" aria-hidden="true">
          <div className="landing-hero-badge">
            <i className="bi bi-graph-up-arrow" /> +38 % retención
          </div>
          <div className="landing-phone">
            <div className="landing-phone-top">
              <span className="landing-chip">Score 9.1</span>
              <span>0:46 · 9:16</span>
            </div>
            <div className="landing-phone-screen">
              <div className="landing-wave">
                {WAVE_BARS.map((i) => (
                  <span key={i} style={{ animationDelay: `${(i % 9) * 0.12}s` }} />
                ))}
              </div>
              <p className="landing-phone-sub">
                nadie te dice <em>esto</em>
              </p>
            </div>
            <div>
              <div className="landing-phone-bar">
                <span style={{ width: '82%' }} />
              </div>
              <div className="landing-phone-pipeline">
                {PREVIEW_STEPS.map((item) => (
                  <span key={item.label}>
                    <i className={`bi ${item.icon}`} /> {item.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="landing-container">
        <dl className="landing-stats">
          {HERO_STATS.map((stat) => (
            <div key={stat.label}>
              <dd className="landing-stat-value">{stat.value}</dd>
              <dt className="landing-stat-label">{stat.label}</dt>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
