import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import LandingAbout from '@/components/landing/LandingAbout'
import LandingFeatures from '@/components/landing/LandingFeatures'
import LandingFooter from '@/components/landing/LandingFooter'
import LandingHero from '@/components/landing/LandingHero'
import LandingHowItWorks from '@/components/landing/LandingHowItWorks'
import LandingNav from '@/components/landing/LandingNav'
import { applyLandingSeo } from '@/components/landing/landingSeo'

/**
 * Landing pública de ClipsAI en `/` (Issue 32).
 *
 * - No requiere autenticación: es la anteportada para usuarios anónimos y para los
 *   revisores de Meta / Google / TikTok, que necesitan una URL pública con aviso
 *   de privacidad y contacto.
 * - Accible también con sesión activa: no redirige a /dashboard.
 */
export default function LandingPage() {
  useEffect(() => {
    applyLandingSeo()
  }, [])

  return (
    <div id="top" className="landing">
      <a href="#contenido" className="landing-skip-link">
        Saltar al contenido
      </a>
      <div className="landing-shell">
        <LandingNav />
        <main id="contenido" className="landing-main">
          <LandingHero />
          <LandingHowItWorks />
          <LandingAbout />
          <LandingFeatures />
          <section className="landing-container" aria-labelledby="cta-final-title">
            <div className="landing-cta-band">
              <h2 id="cta-final-title" className="landing-heading">
                Grabá una vez. <span className="landing-accent">Aparecé todos los días.</span>
              </h2>
              <p className="landing-lead">
                Tus mejores momentos, listos para crecer en redes.
              </p>
              <div className="landing-cta-row landing-cta-row-center">
                <Link to="/auth" className="landing-btn landing-btn-primary">
                  Probar gratis <i className="bi bi-arrow-right" aria-hidden="true" />
                </Link>
                <a href="#features" className="landing-btn landing-btn-ghost">
                  Ver funciones
                </a>
              </div>
            </div>
          </section>
        </main>
        <LandingFooter />
      </div>
    </div>
  )
}
