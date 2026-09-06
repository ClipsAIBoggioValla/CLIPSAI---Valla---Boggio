export default function Footer() {
  return (
    <footer className="footer-custom">
      <div className="footer-left">
        <span className="footer-logo">
          <i className="bi bi-asterisk" /> clipsai
        </span>
        <span className="footer-separator">|</span>
        <span className="footer-copy">
          © 2026 Hecho con <i className="bi bi-heart-fill text-danger" style={{ color: '#EF4444', fontSize: '0.75rem' }} /> por clipsai • Spark Admin
        </span>
      </div>
      <div className="footer-right">
        <ul className="footer-links">
          <li>
            <a href="/dashboard" className="footer-link">
              Overview
            </a>
          </li>
          <li>
            <a href="/clips" className="footer-link">
              Biblioteca
            </a>
          </li>
          <li>
            <a href="#" className="footer-link">
              Ayuda
            </a>
          </li>
          <li>
            <a href="#" className="footer-link">
              Status <span className="status-dot" />
            </a>
          </li>
        </ul>
      </div>
    </footer>
  )
}
