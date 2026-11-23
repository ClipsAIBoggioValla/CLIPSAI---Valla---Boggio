<script setup lang="ts">
import LegalLayout from '@/components/legal/LegalLayout.vue'
</script>

<template>
  <LegalLayout
    title="Eliminación de Datos"
    subtitle="Cómo solicitar la revocación o borrado de tus datos"
    icon="bi-trash"
  >
    <div class="legal-highlight">
      <strong>Tu derecho:</strong> Podés solicitar en cualquier momento la eliminación completa de tu cuenta
      y todos los datos personales asociados. Meta, Google y TikTok exigen que este proceso sea claro y
      accesible.
    </div>

    <section class="legal-section">
      <h2 class="legal-section-title">1. Cómo solicitar la eliminación</h2>
      <p>
        Para solicitar la eliminación de tus datos, enviá un correo electrónico a
        <a href="mailto:privacidad@clipsai.xyz">privacidad@clipsai.xyz</a> con el asunto
        <strong>"Solicitud de eliminación de datos"</strong> y la dirección de correo asociada a tu cuenta.
      </p>
      <p>
        También podés eliminar tu cuenta directamente desde la aplicación en
        <strong>Configuración → Cuenta → Eliminar cuenta</strong>.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">2. Qué datos se eliminan</h2>
      <ul>
        <li>Tu cuenta de usuario y credenciales de acceso.</li>
        <li>Los videos que subiste y sus transcripciones.</li>
        <li>Los clips generados a partir de tus videos.</li>
        <li>Los tokens de acceso OAuth a YouTube, Instagram y TikTok.</li>
        <li>Los datos de uso y métricas asociados a tu cuenta.</li>
      </ul>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">3. Plazo de eliminación</h2>
      <p>
        Procesamos las solicitudes de eliminación dentro de los <strong>30 días</strong> hábiles. Recibirás
        una confirmación por correo electrónico cuando la eliminación se haya completado.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">4. Datos que podemos conservar</h2>
      <p>
        Algunos datos pueden conservarse de forma anonimizada para cumplir obligaciones legales o resolver
        disputas. Estos datos no te identifican personalmente y no se usan para ningún otro fin.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">5. Revocación de acceso OAuth</h2>
      <p>
        Si solo querés revocar el acceso de ClipsAI a tus redes sociales sin eliminar tu cuenta, podés
        hacerlo desde <strong>Configuración → Integraciones</strong> desconectando cada red, o directamente
        desde la configuración de aplicaciones de YouTube, Instagram o TikTok.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">6. Contacto</h2>
      <p>
        Si tenés preguntas sobre la eliminación de datos, escribinos a
        <a href="mailto:privacidad@clipsai.xyz">privacidad@clipsai.xyz</a>.
      </p>
    </section>

    <p class="legal-updated">Última actualización: octubre de 2026</p>
  </LegalLayout>
</template>