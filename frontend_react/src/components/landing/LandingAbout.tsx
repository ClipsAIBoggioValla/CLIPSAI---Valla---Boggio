import { LANDING_ABOUT } from './landingData'

/** Beneficios cotidianos para publicar más y editar menos. */
export default function LandingAbout() {
  return (
    <section id="sobre-nosotros" className="landing-section" aria-labelledby="sobre-nosotros-title">
      <div className="landing-container">
        <div className="landing-section-head">
          <span className="landing-eyebrow">
            <i className="bi bi-stars" aria-hidden="true" /> Beneficios
          </span>
          <h2 id="sobre-nosotros-title" className="landing-heading">
            Menos edición, <span className="landing-accent">más alcance.</span>
          </h2>
          <p className="landing-lead">
            Tus mejores momentos, listos para compartir en minutos.
          </p>
        </div>

        <div className="landing-about-grid">
          {LANDING_ABOUT.map((pillar) => (
            <article key={pillar.title} className="landing-about-card">
              <span className="landing-about-icon" aria-hidden="true">
                <i className={`bi ${pillar.icon}`} />
              </span>
              <h3 className="landing-about-title">{pillar.title}</h3>
              <p className="landing-about-text">{pillar.text}</p>
            </article>
          ))}
        </div>

        <aside className="landing-panel mt-6">
          <h3 className="landing-panel-title">Un video adentro, tres redes publicadas.</h3>
          <ul className="landing-panel-list">
            <li><i className="bi bi-check-circle-fill" aria-hidden="true" /><span>Subtítulos y gancho inicial.</span></li>
            <li><i className="bi bi-check-circle-fill" aria-hidden="true" /><span>Formato vertical listo para compartir.</span></li>
            <li><i className="bi bi-check-circle-fill" aria-hidden="true" /><span>Publicación automática en tus redes.</span></li>
          </ul>
        </aside>
      </div>
    </section>
  )
}
