import { Link } from 'react-router-dom'
import { HERO_STATS } from './landingData'

const WAVE_BARS = Array.from({ length: 26 }, (_, i) => i)

const PIPELINE = [
  { icon: 'bi-soundwave', label: 'Audio analizado: 50 momentos' },
  { icon: 'bi-stars', label: 'IA: 10 clips con score' },
  { icon: 'bi-phone', label: 'Render 9:16 + subtítulos ASS' },
  { icon: 'bi-send-check', label: 'Publicado en 3 redes' },
]

/** Hero: titular de impacto, propuesta de valor y CTA "Probar gratis" → /auth. */
export default function LandingHero() {
  return (
    <section className="landing-hero" aria-labelledby="hero-title">
      <div className="landing-container landing-hero-grid">
        <div>
          <span className="landing-eyebrow">
            <i className="bi bi-stars" aria-hidden="true" /> Motor IA propio · audio real · autopublicación
          </span>
          <h1 id="hero-title" className="landing-heading">
            De un video largo a <span className="landing-accent">clips que se publican solos</span>
          </h1>
          <p className="landing-lead">
            ClipsAI escucha el audio de tu video, encuentra con IA los momentos que enganchan, los corta en
            vertical 9:16 con subtítulos palabra por palabra y los publica en YouTube, Instagram y TikTok. Sin
            editor, sin exporting a mano, sin posts que quedan en el borrador.
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
            <i className="bi bi-shield-check" aria-hidden="true" /> Sin tarjeta de crédito · tu video solo se usa
            para generar tus clips
          </p>
        </div>

        <div className="landing-hero-visual" aria-hidden="true">
          <div className="landing-hero-badge">
            <i className="bi bi-graph-up-arrow" /> +38 % retención
          </div>
          <div className="landing-phone">
            <div className="landing-phone-top">
              <span className="landing-chip">SCORE 9.1</span>
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
                {PIPELINE.map((item) => (
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