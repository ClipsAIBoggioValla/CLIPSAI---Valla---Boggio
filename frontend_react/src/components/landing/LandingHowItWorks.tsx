import { useRef, useState, type KeyboardEvent } from 'react'
import { LANDING_STEPS } from './landingData'

/** "Cómo funciona": 3 pasos (cargar video → análisis IA → publicación) navegables con mouse y teclado. */
export default function LandingHowItWorks() {
  const [active, setActive] = useState(0)
  const tabsRef = useRef<Array<HTMLButtonElement | null>>([])
  const step = LANDING_STEPS[active]

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = LANDING_STEPS.length - 1
    let next: number | null = null
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = index === last ? 0 : index + 1
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = index === 0 ? last : index - 1
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = last
    if (next === null) return
    event.preventDefault()
    setActive(next)
    tabsRef.current[next]?.focus()
  }

  return (
    <section id="como-funciona" className="landing-section" aria-labelledby="como-funciona-title">
      <div className="landing-container">
        <div className="landing-section-head landing-section-head-center">
          <span className="landing-eyebrow">
            <i className="bi bi-signpost-split" aria-hidden="true" /> Cómo funciona
          </span>
          <h2 id="como-funciona-title" className="landing-heading">
            Tres pasos, <span className="landing-accent">un solo trabajo pendiente</span>
          </h2>
          <p className="landing-lead">
            El mismo pipeline que corre en producción, paso a paso. Elegí un paso para ver qué pasa por debajo.
          </p>
        </div>

        <div className="landing-steps">
          <div className="landing-step-list" role="tablist" aria-label="Pasos de ClipsAI" aria-orientation="vertical">
            {LANDING_STEPS.map((item, index) => (
              <button
                key={item.id}
                id={`step-tab-${item.id}`}
                ref={(el) => {
                  tabsRef.current[index] = el
                }}
                type="button"
                role="tab"
                className="landing-step-tab"
                aria-selected={index === active}
                aria-controls={`step-panel-${item.id}`}
                tabIndex={index === active ? 0 : -1}
                onClick={() => setActive(index)}
                onKeyDown={(event) => onKeyDown(event, index)}
              >
                <span className="landing-step-index" aria-hidden="true">
                  {index + 1}
                </span>
                <span>
                  <span className="landing-step-tab-title">{item.title}</span>
                  <span className="landing-step-tab-hint">{item.hint}</span>
                </span>
              </button>
            ))}
          </div>

          <div
            id={`step-panel-${step.id}`}
            role="tabpanel"
            aria-labelledby={`step-tab-${step.id}`}
            tabIndex={0}
            className="landing-panel"
          >
            <h3 className="landing-panel-title">
              <i className={`bi ${step.icon} me-2 text-[#B4F105]`} aria-hidden="true" />
              {step.title}
            </h3>
            <p className="landing-panel-text">{step.summary}</p>
            <ul className="landing-panel-list">
              {step.bullets.map((bullet) => (
                <li key={bullet}>
                  <i className="bi bi-check-circle-fill" aria-hidden="true" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>

            <div className="landing-monitor" aria-hidden="true">
              <p className="landing-monitor-head">
                <i className={`bi ${step.icon}`} /> {step.monitorTitle}
              </p>
              <div className="landing-monitor-rows">
                {step.rows.map((row) => (
                  <div key={row.label} className="landing-monitor-row">
                    <div className="landing-monitor-row-top">
                      <span className="landing-monitor-row-label">{row.label}</span>
                      <span className={`landing-monitor-badge ${row.tone}`}>{row.badge}</span>
                    </div>
                    <span className="landing-monitor-row-meta">{row.meta}</span>
                    {row.progress !== undefined && (
                      <span className="landing-monitor-bar">
                        <span style={{ width: `${row.progress}%` }} />
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}