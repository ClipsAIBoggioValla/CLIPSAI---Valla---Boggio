import { LANDING_FEATURES } from './landingData'

/** Features grid: corte 9:16, subtítulos dinámicos y autopublicación, más el resto del flujo. */
export default function LandingFeatures() {
  return (
    <section id="features" className="landing-section" aria-labelledby="features-title">
      <div className="landing-container">
        <div className="landing-section-head landing-section-head-center">
          <span className="landing-eyebrow">
            <i className="bi bi-grid-3x3-gap" aria-hidden="true" /> Features
          </span>
          <h2 id="features-title" className="landing-heading">
            Todo lo que hace falta <span className="landing-accent">para publicar</span>
          </h2>
          <p className="landing-lead">
            Del video crudo al post publicado: formato, subtítulos, publicación y métricas en el mismo lugar.
          </p>
        </div>

        <div className="landing-features-grid">
          {LANDING_FEATURES.map((feature) => (
            <article key={feature.title} className="landing-feature-card">
              <span className="landing-feature-chip">{feature.chip}</span>
              <span className="landing-feature-icon" aria-hidden="true">
                <i className={`bi ${feature.icon}`} />
              </span>
              <h3 className="landing-feature-title">{feature.title}</h3>
              <p className="landing-feature-text">{feature.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}