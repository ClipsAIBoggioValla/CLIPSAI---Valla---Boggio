import LegalLayout from '@/components/legal/LegalLayout'

/** Política de privacidad — requisito para validación de APIs (Meta/Google/TikTok). */
export default function PrivacyPage() {
  return (
    <LegalLayout
      title="Política de Privacidad"
      subtitle="Cómo ClipsAI recopila, usa y protege tus datos"
      icon="bi-shield-lock"
    >
      <section className="legal-section">
        <h2 className="legal-section-title">1. Datos que recopilamos</h2>
        <p>
          <strong>Datos de cuenta:</strong> dirección de correo electrónico, nombre (opcional) y contraseña
          cifrada. Nunca almacenamos tu contraseña en texto plano.
        </p>
        <p>
          <strong>Contenido subido:</strong> los videos y transcripciones que cargás para generar clips. Este
          contenido se procesa en nuestros servidores y se almacena de forma segura.
        </p>
        <p>
          <strong>Datos de autenticación social:</strong> si conectás tu cuenta de YouTube, Instagram o TikTok,
          recibimos un token de acceso OAuth que nos permite publicar en tu nombre. No almacenamos tus
          contraseñas de redes sociales.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">2. Cómo usamos tus datos</h2>
        <ul>
          <li>Procesar los videos que subís y generar clips con subtítulos y hooks.</li>
          <li>Publicar clips en las redes sociales que conectés mediante OAuth.</li>
          <li>Enviarte notificaciones sobre el estado de tus trabajos (completado, error).</li>
          <li>Mejorar la calidad del motor de IA y la precisión del scoring de viralidad.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">3. Con quién compartimos tus datos</h2>
        <p>
          <strong>Proveedores de IA:</strong> los videos y transcripciones se envían a modelos de lenguaje
          (Anthropic, OpenRouter, OpenAI o DeepSeek) para generar títulos, hooks y scores. Estos proveedores
          no usan los datos para entrenar modelos.
        </p>
        <p>
          <strong>Redes sociales:</strong> los clips se publican en YouTube, Instagram o TikTok únicamente
          cuando vos lo solicitás.
        </p>
        <p>
          <strong>No vendemos tus datos.</strong> ClipsAI no comparte información personal con terceros con
          fines comerciales.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">4. Seguridad</h2>
        <p>
          Las contraseñas se almacenan con cifrado bcrypt. Los tokens OAuth se guardan cifrados en nuestra
          base de datos. Las conexiones entre tu navegador y nuestros servidores usan HTTPS/TLS.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">5. Tus derechos</h2>
        <p>
          Podés solicitar en cualquier momento:
        </p>
        <ul>
          <li>Acceso a los datos personales que tenemos sobre vos.</li>
          <li>Rectificación de datos incorrectos o incompletos.</li>
          <li>Eliminación de tu cuenta y todos los datos asociados.</li>
          <li>Revocación del acceso OAuth a tus redes sociales.</li>
        </ul>
        <p>
          Para ejercer estos derechos, escribinos a{' '}
          <a href="mailto:privacidad@clipsai.xyz">privacidad@clipsai.xyz</a>.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">6. Contacto</h2>
        <p>
          Si tenés preguntas sobre esta política, contactanos a{' '}
          <a href="mailto:privacidad@clipsai.xyz">privacidad@clipsai.xyz</a>.
        </p>
      </section>

      <p className="legal-updated">Última actualización: octubre de 2026</p>
    </LegalLayout>
  )
}