<template>
  <footer class="footer-custom">
    <div class="footer-left">
      <span class="footer-logo"><i class="bi bi-asterisk" /> clipsai</span>
      <span class="footer-separator">|</span>
      <span class="footer-copy">© 2026 Hecho con <i class="bi bi-heart-fill" style="color:#EF4444; font-size:0.75rem" /> por clipsai • Spark Admin</span>
    </div>
    <div class="footer-right">
      <ul class="footer-links">
        <li><RouterLink to="/dashboard" class="footer-link">Overview</RouterLink></li>
        <li><RouterLink to="/clips" class="footer-link">Biblioteca</RouterLink></li>
        <li><a href="#" class="footer-link" @click.prevent> Ayuda </a></li>
        <li><a href="#" class="footer-link" @click.prevent> Status <span class="status-dot" /></a></li>
      </ul>
    </div>
  </footer>
</template>
