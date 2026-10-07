import type { ReactNode } from 'react'

interface LegalLayoutProps {
  title: string
  subtitle: string
  icon: string
  children: ReactNode
}

/** Layout compartido para las páginas legales (Issue 33). */
export default function LegalLayout({ title, subtitle, icon, children }: LegalLayoutProps) {
  return (
    <div className="legal-page">
      <div className="legal-container">
        <header className="legal-header">
          <span className="legal-icon" aria-hidden="true">
            <i className={`bi ${icon}`} />
          </span>
          <h1 className="legal-title">{title}</h1>
          <p className="legal-subtitle">{subtitle}</p>
        </header>
        <div className="legal-content">{children}</div>
      </div>
    </div>
  )
}