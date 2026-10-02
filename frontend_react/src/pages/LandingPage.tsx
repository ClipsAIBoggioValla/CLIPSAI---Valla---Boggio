import { useEffect } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
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
 * - Con sesión activa se redirige a `/dashboard` para no interrumpir el trabajo.
 */
export default function LandingPage() {
  const { user, isLoading } = useAuth()

  useEffect(() => {
    applyLandingSeo()
  }, [])

  if (!isLoading && user) {
    return <Navigate to="/dashboard" replace />
  }

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
                Subí tu video y mirá <span className="landing-accent">qué clip sale primero</span>
              </h2>
              <p className="landing-lead">
                Creás la cuenta gratis, subís un video largo y en minutos tenés clips verticales con subtítulos,
                score de viralidad y publicación automática.
              </p>
              <div className="landing-cta-row landing-cta-row-center">
                <Link to="/auth" className="landing-btn landing-btn-primary">
                  Probar gratis <i className="bi bi-arrow-right" aria-hidden="true" />
                </Link>
                <a href="#features" className="landing-btn landing-btn-ghost">
                  Ver features
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