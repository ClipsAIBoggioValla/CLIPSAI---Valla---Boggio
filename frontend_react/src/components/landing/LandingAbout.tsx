import { LANDING_ABOUT, LANDING_STACK } from './landingData'

/** "Sobre nosotros": motor de IA, análisis de audio y scoring de viralidad. */
export default function LandingAbout() {
  return (
    <section id="sobre-nosotros" className="landing-section" aria-labelledby="sobre-nosotros-title">
      <div className="landing-container">
        <div className="landing-section-head">
          <span className="landing-eyebrow">
            <i className="bi bi-code-slash" aria-hidden="true" /> Sobre nosotros
          </span>
          <h2 id="sobre-nosotros-title" className="landing-heading">
            El motor por debajo <span className="landing-accent">del botón</span>
          </h2>
          <p className="landing-lead">
            ClipsAI no es una caja negra: escribimos el pipeline completo —audio, prompt, scoring, render y
            publicación— y lo auditamos en cada job.
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
              <code className="landing-about-code">{pillar.code}</code>
            </article>
          ))}
        </div>

        <div className="landing-stack" aria-label="Stack tecnológico de ClipsAI">
          {LANDING_STACK.map((tech) => (
            <span key={tech}>{tech}</span>
          ))}
        </div>
      </div>
    </section>
  )
}