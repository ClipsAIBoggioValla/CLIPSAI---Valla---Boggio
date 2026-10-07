<script setup lang="ts">
import LegalLayout from '@/components/legal/LegalLayout.vue'
</script>

<template>
  <LegalLayout title="Términos y Condiciones" subtitle="Reglas de uso del servicio ClipsAI" icon="bi-file-text">
    <section class="legal-section">
      <h2 class="legal-section-title">1. Aceptación de los términos</h2>
      <p>
        Al crear una cuenta o usar ClipsAI, aceptás estos términos y condiciones. Si no estás de acuerdo,
        no uses el servicio.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">2. Descripción del servicio</h2>
      <p>
        ClipsAI es una plataforma que analiza videos largos mediante inteligencia artificial, identifica los
        momentos con mayor potencial viral, los corta en formato vertical 9:16 con subtítulos dinámicos y
        los publica automáticamente en YouTube, Instagram y TikTok.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">3. Cuenta de usuario</h2>
      <ul>
        <li>Debés proporcionar una dirección de correo electrónico válida.</li>
        <li>Sos responsable de mantener la confidencialidad de tu contraseña.</li>
        <li>Una persona puede tener solo una cuenta activa.</li>
        <li>Podemos suspender cuentas que violen estos términos.</li>
      </ul>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">4. Uso aceptable</h2>
      <p>Te comprometes a no usar ClipsAI para:</p>
      <ul>
        <li>Violar derechos de autor o propiedad intelectual de terceros.</li>
        <li>Publicar contenido ilegal, difamatorio o que incite al odio.</li>
        <li>Intentar acceder sin autorización a nuestros sistemas.</li>
        <li>Usar el servicio para spam o actividades fraudulentas.</li>
      </ul>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">5. Propiedad intelectual</h2>
      <p>
        <strong>Vos conservás todos los derechos</strong> sobre los videos y contenido que subís. ClipsAI
        solo procesa tu contenido para generar los clips que solicitaste.
      </p>
      <p>
        El software, diseño y marca de ClipsAI son propiedad de ClipsAI y están protegidos por las leyes de
        propiedad intelectual aplicables.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">6. Limitación de responsabilidad</h2>
      <p>
        ClipsAI se proporciona "tal cual". No garantizamos que el servicio esté libre de errores o
        interrupciones. No somos responsables por daños indirectos, incidentales o consecuentes derivados del
        uso del servicio.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">7. Modificaciones</h2>
      <p>
        Podemos actualizar estos términos en cualquier momento. Te notificaremos por correo electrónico sobre
        cambios significativos. El uso continuado del servicio implica la aceptación de los nuevos términos.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">8. Ley aplicable</h2>
      <p>
        Estos términos se rigen por las leyes de la República Argentina. Cualquier disputa se resolverá ante
        los tribunales competentes de la Ciudad Autónoma de Buenos Aires.
      </p>
    </section>

    <section class="legal-section">
      <h2 class="legal-section-title">9. Contacto</h2>
      <p>
        Para consultas sobre estos términos, escribinos a
        <a href="mailto:legal@clipsai.xyz">legal@clipsai.xyz</a>.
      </p>
    </section>

    <p class="legal-updated">Última actualización: octubre de 2026</p>
  </LegalLayout>
</template>