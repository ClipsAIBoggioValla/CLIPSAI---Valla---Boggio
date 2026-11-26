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
          recibimos los datos de autorización OAuth y tokens necesarios para las funciones que habilitás. No
          recibimos ni almacenamos la contraseña de tu red social. Los permisos solicitados se limitan a las
          funciones de ClipsAI: YouTube (`youtube.readonly` y `youtube.upload`), Instagram
          (`instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` y
          `business_management`) y TikTok (`user.info.basic`, `video.upload` y `video.publish`).
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">2. Cómo usamos tus datos</h2>
        <ul>
          <li>Procesar los videos que subís y generar clips con subtítulos y hooks.</li>
          <li>Conectar, consultar la información básica necesaria y publicar clips solo en las redes que autorizás.</li>
          <li>Enviarte notificaciones sobre el estado de tus trabajos (completado, error).</li>
          <li>Generar títulos, hooks y puntuaciones para los clips que solicitás.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">3. Con quién compartimos tus datos</h2>
        <p>
          <strong>Proveedores de IA:</strong> los videos y transcripciones se envían a modelos de lenguaje
          (Anthropic, OpenRouter, OpenAI o DeepSeek, según la configuración del servicio) para generar títulos,
          hooks y puntuaciones. El contenido se comparte solo en la medida necesaria para prestar esa función y
          queda sujeto a las condiciones y políticas de privacidad del proveedor correspondiente.
        </p>
        <p>
          <strong>Google/YouTube, Meta/Instagram y TikTok:</strong> los datos de autorización se usan para
          conectar la cuenta y los clips se envían a la plataforma correspondiente cuando iniciás una
          publicación o tenés una programación configurada. Cada plataforma trata esos datos según sus propias
          políticas. Revocar la conexión impide nuevas operaciones desde ClipsAI; no elimina publicaciones ya
          hechas en la plataforma.
        </p>
        <p>
          <strong>No vendemos tus datos.</strong> ClipsAI no comparte información personal con terceros con
          fines comerciales.
        </p>
      </section>

      <section className="legal-section">
        <h2 className="legal-section-title">4. Seguridad</h2>
        <p>
          Las contraseñas se almacenan con hash bcrypt. Los tokens OAuth se cifran en reposo y se usan para
          operar únicamente la integración autorizada. Las conexiones entre tu navegador y nuestros servidores
          de producción usan HTTPS/TLS.
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

      <p className="legal-updated">Última actualización: noviembre de 2026</p>
    </LegalLayout>
  )
}
