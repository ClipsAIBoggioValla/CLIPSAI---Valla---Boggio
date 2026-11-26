import LegalLayout from '@/components/legal/LegalLayout'

/** Términos y condiciones — requisito para validación de APIs (Meta/Google/TikTok). */
export default function TermsPage() {
  return (
    <LegalLayout
      title="Términos y Condiciones"
      subtitle="Reglas de uso del servicio ClipsAI"
      icon="bi-file-text"
    >
      <section className="legal-section">
        <h2 className="legal-section-title">1. Aceptación de los términos</h2>
        <p>
          Al crear una cuenta o usar ClipsAI, aceptás estos términos y condiciones. Si no estás de acuerdo,
          no uses el servicio.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">2. Descripción del servicio</h2>
        <p>
          ClipsAI es una plataforma que analiza videos largos mediante inteligencia artificial, identifica los
          momentos con mayor potencial viral, los corta en formato vertical 9:16 con subtítulos dinámicos y
          permite publicarlos en YouTube, Instagram y TikTok. Para publicar, tenés que conectar y autorizar
          cada cuenta e iniciar la publicación o configurar una programación desde ClipsAI.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">3. Integraciones con redes sociales</h2>
        <p>
          Al conectar una cuenta, autorizás a ClipsAI mediante OAuth a solicitar únicamente los permisos
          necesarios para la integración: YouTube (`youtube.readonly` y `youtube.upload`), Instagram
          (`instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` y
          `business_management`) y TikTok
          (`user.info.basic`, `video.upload` y `video.publish`). No compartas tu contraseña de esas plataformas
          con ClipsAI. Podés desconectar una integración desde la aplicación o revocar el acceso en la
          configuración de seguridad de la plataforma. La revocación no retira publicaciones ya realizadas.
        </p>
        <p>
          El uso de las plataformas conectadas también está sujeto a sus propios términos y políticas. Podés
          solicitar la eliminación de tu cuenta y datos en <a href="/eliminacion-de-datos">Eliminación de datos</a>.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">4. Cuenta de usuario</h2>
        <ul>
          <li>Debés proporcionar una dirección de correo electrónico válida.</li>
          <li>Sos responsable de mantener la confidencialidad de tu contraseña.</li>
          <li>Una persona puede tener solo una cuenta activa.</li>
          <li>Podemos suspender cuentas que violen estos términos.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">5. Uso aceptable</h2>
        <p>Te comprometes a no usar ClipsAI para:</p>
        <ul>
          <li>Violar derechos de autor o propiedad intelectual de terceros.</li>
          <li>Publicar contenido ilegal, difamatorio o que incite al odio.</li>
          <li>Intentar acceder sin autorización a nuestros sistemas.</li>
          <li>Usar el servicio para spam o actividades fraudulentas.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">6. Propiedad intelectual</h2>
        <p>
          <strong>Vos conservás todos los derechos</strong> sobre los videos y contenido que subís. ClipsAI
          solo procesa tu contenido para generar los clips que solicitaste.
        </p>
        <p>
          El software, diseño y marca de ClipsAI son propiedad de ClipsAI y están protegidos por las leyes de
          propiedad intelectual aplicables.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">7. Limitación de responsabilidad</h2>
        <p>
          ClipsAI se proporciona "tal cual". No garantizamos que el servicio esté libre de errores o
          interrupciones. No somos responsables por daños indirectos, incidentales o consecuentes derivados del
          uso del servicio.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">8. Modificaciones</h2>
        <p>
          Podemos actualizar estos términos en cualquier momento. Te notificaremos por correo electrónico sobre
          cambios significativos. El uso continuado del servicio implica la aceptación de los nuevos términos.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">9. Ley aplicable</h2>
        <p>
          Estos términos se rigen por las leyes de la República Argentina. Cualquier disputa se resolverá ante
          los tribunales competentes de la Ciudad Autónoma de Buenos Aires.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">10. Contacto</h2>
        <p>
          Para consultas sobre estos términos, escribinos a{' '}
          <a href="mailto:legal@clipsai.xyz">legal@clipsai.xyz</a>.
        </p>
      </section>

      <p className="legal-updated">Última actualización: noviembre de 2026</p>
    </LegalLayout>
  )
}
