import { LANDING_FEATURES } from './landingData'

/** Funciones listas para crear y compartir clips. */
export default function LandingFeatures() {
  return (
    <section id="features" className="landing-section" aria-labelledby="features-title">
      <div className="landing-container">
        <div className="landing-section-head landing-section-head-center">
          <span className="landing-eyebrow">
            <i className="bi bi-grid-3x3-gap" aria-hidden="true" /> Funciones
          </span>
          <h2 id="features-title" className="landing-heading">
            Todo listo para <span className="landing-accent">publicar sin fricción.</span>
          </h2>
          <p className="landing-lead">
            Creá, encontrá y compartí tus clips desde un solo lugar.
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
