# Pase a producción y revisión OAuth de ClipsAI

Checklist operativo para los dominios de ejemplo `https://clipsai.xyz` (web) y
`https://api.clipsai.xyz` (API). La aprobación, el estado Live y la verificación de dominios se
gestionan en las consolas de cada proveedor y no pueden completarse desde este repositorio. Los nombres
de menús pueden variar; confirmar el flujo vigente en la consola antes de enviar.

## 1. Preparación común

- [ ] Desplegar frontend y API con certificados HTTPS válidos, renovación automática y sin contenido mixto.
- [ ] Confirmar que `https://clipsai.xyz/` y las páginas de privacidad, términos y eliminación abren sin
  iniciar sesión ni redirecciones a localhost:
  - `https://clipsai.xyz/politica-de-privacidad`
  - `https://clipsai.xyz/terminos-y-condiciones`
  - `https://clipsai.xyz/eliminacion-de-datos`
- [ ] Verificar los enlaces desde el pie de página, la respuesta directa de cada URL y el fallback de rutas SPA.
  Revisar que `https://clipsai.xyz/sitemap.xml` incluya las tres páginas legales.
- [ ] Completar los contactos y las prácticas legales para que reflejen el tratamiento real, retención,
  proveedores de IA, respuesta a eliminación y revocación. La copia del repo es una base de revisión, no un
  dictamen legal.
- [ ] Crear/confirmar en el gestor de secretos las credenciales de producción y `VAULT_KEY`; configurar
  `APP_ENV=production`, secretos fuertes, HTTPS y URLs/callbacks exactos del `.env.example`. No poner secretos
  en el frontend, issues, grabaciones ni commits.
- [ ] Mantener OAuth state/redirects restringidos a los valores registrados; probar conexión, refresh,
  desconexión y eliminación con cuentas de prueba antes del envío.
- [ ] Usar cuentas, páginas y videos propios o con autorización explícita. Revisar que el título, descripción,
  privacidad/audiencia y destino sean claros antes de publicar.

## 2. Google Cloud Console — YouTube

- [ ] Seleccionar el proyecto de producción y habilitar **YouTube Data API v3**.
- [ ] Configurar la pantalla de consentimiento OAuth como aplicación externa (si aplica): nombre y logo
  coherentes, correo de soporte y contacto del desarrollador, dominios autorizados y enlaces HTTPS de inicio,
  privacidad y términos. Verificar la propiedad del dominio según el flujo de Google (por ejemplo, Search
  Console) y que el dominio de la página de inicio/privacidad coincide con el dominio autorizado.
- [ ] Solicitar solo los scopes usados por la integración. El servicio solicita
  `https://www.googleapis.com/auth/youtube.readonly` y
  `https://www.googleapis.com/auth/youtube.upload`; describir en la solicitud por qué se necesitan para
  identificar el canal y subir el clip cuando la persona lo solicita.
- [ ] En **Clients**, registrar el cliente OAuth web y el redirect URI exacto
  `https://api.clipsai.xyz/auth/social/youtube/callback`. Debe coincidir carácter por carácter con
  `GOOGLE_REDIRECT_URI`.
- [ ] Completar el proceso de verificación OAuth y cualquier revisión/política de YouTube que muestre la
  consola para el scope de carga. Adjuntar explicación de uso mínimo, enlaces legales públicos y grabación.
- [ ] Antes de aprobar, usar modo de prueba solo con usuarios de prueba explícitos; para producción, comprobar
  que el estado/publicación de la app y el scope requerido estén aprobados y que no aparezca el aviso de app no
  verificada.
- [ ] Cargar el Client ID/Secret solo en el gestor de secretos del backend. Probar callback y publicación con
  un canal de prueba autorizado y confirmar resultado/error de API.

**Evidencia para adjuntar:** captura del scope aprobado/estado de verificación y grabación del flujo descrito
en la sección 5. No mostrar secretos ni tokens.

## 3. Meta for Developers — Instagram

- [ ] Configurar la app de producción con el producto de Instagram/API de publicación compatible con la
  cuenta; revisar que la cuenta de Instagram y la Página asociada cumplen los requisitos vigentes de Meta.
- [ ] En la configuración básica, completar nombre, icono, correo de contacto, dominio de la app y URLs HTTPS
  de privacidad y eliminación de datos. Usar `https://clipsai.xyz/eliminacion-de-datos` como instrucciones
  públicas de eliminación, salvo que el dashboard solicite un endpoint callback distinto.
- [ ] Registrar el redirect URI exacto
  `https://api.clipsai.xyz/auth/social/instagram/callback` y comprobarlo contra `INSTAGRAM_REDIRECT_URI`.
- [ ] Solicitar revisión/Advanced Access para `instagram_content_publish` y los permisos adicionales que
  realmente usa la integración (`instagram_basic`, `pages_show_list`, `pages_read_engagement` y
  `business_management`). Para cada permiso, aportar justificación, caso de uso y grabación funcional; quitar
  permisos no necesarios si el flujo aprobado lo permite.
- [ ] Completar verificaciones de negocio/portafolio que el panel exija. Después de las aprobaciones, cambiar
  la app a **Live** y validar que el login y publicación funcionan con un usuario que no sea rol/tester de la
  app.
- [ ] Guardar App ID/Secret en el gestor de secretos. Confirmar que desconectar/revocar elimina credenciales
  locales y que publicar requiere acción iniciada por la persona usuaria.

**Evidencia para adjuntar:** capturas de Live y de los permisos aprobados, además de la grabación de conexión y
publicación. Verificar políticas y requisitos de cuenta en el dashboard; Meta puede cambiar disponibilidad,
nombres de productos y requisitos de acceso.

## 4. TikTok for Developers

- [ ] Completar perfil de desarrollador y datos de la app: nombre, icono, descripción, política de privacidad,
  términos, instrucciones de eliminación y dominio web HTTPS público.
- [ ] Verificar la propiedad del dominio según la opción ofrecida en Developer Portal (p. ej. DNS, archivo o
  meta-tag). Completar la verificación para el dominio usado por la app y conservar evidencia del estado
  verificado.
- [ ] Configurar el redirect URI exacto `https://api.clipsai.xyz/auth/social/tiktok/callback` en la app y en
  `TIKTOK_REDIRECT_URI`.
- [ ] Solicitar los scopes mínimos requeridos por la implementación: `user.info.basic`, `video.upload` y
  `video.publish`. Enviar `video.publish` a auditoría/revisión y aportar propósito, consentimiento, flujo de
  publicación y controles de usuario. Incluir `video.upload` si el dashboard/API lo exige para este flujo.
- [ ] Adjuntar grabación del flujo real desde autorización hasta publicación, sin cortes que oculten el
  consentimiento o la acción de publicar. Atender observaciones de auditoría antes de habilitar a todos los
  usuarios.
- [ ] Al aprobar, configurar Client Key/Secret en el gestor de secretos. Probar callback, carga, consulta del
  estado de publicación y revocación con una cuenta de prueba autorizada.

**Evidencia para adjuntar:** estado de dominio verificado, estado de auditoría `video.publish` y grabación. El
envío no equivale a aprobación; usar el estado final que muestre TikTok for Developers como criterio.

## 5. Guiones de grabación (una grabación independiente por plataforma)

Preparar tres grabaciones limpias —YouTube, Instagram y TikTok— con cuenta de prueba autorizada, clip no
confidencial y entorno de producción o de revisión autorizado por el proveedor. Capturar pantalla completa,
interfaz legible, idioma consistente y el reloj/fecha si la consola lo solicita. No incluir contraseñas,
Client Secret, access/refresh tokens, datos personales de terceros ni pestañas con información sensible.

En cada video, empezar en la landing pública y mostrar los enlaces visibles de privacidad, términos y
eliminación. Luego entrar en **Integraciones**, conectar la cuenta de prueba, aceptar el consentimiento OAuth,
volver a ClipsAI, seleccionar un clip autorizado, mostrar la acción de publicación, esperar el resultado y
terminar mostrando dónde desconectar. No ocultar ni editar el consentimiento, la acción del usuario ni el
resultado de publicación.

### Grabación Google / YouTube

1. En Integraciones, iniciar la conexión YouTube y mostrar el selector/autorización de Google.
2. Mostrar el nombre de ClipsAI y los permisos visibles para consultar el canal y subir videos; aceptar con la
   cuenta de prueba autorizada. Nunca grabar el formulario de contraseña.
3. Volver a ClipsAI y mostrar el canal conectado. Seleccionar el clip propio, completar título y opciones de
   publicación disponibles, y pulsar **Publicar en YouTube**.
4. Mostrar el estado de carga/resultado y, si la cuenta de prueba lo permite, el video en YouTube Studio o en el
   destino con su visibilidad claramente identificada. Finalizar mostrando cómo desconectar YouTube.

### Grabación Meta / Instagram

1. Iniciar la conexión Instagram desde Integraciones y mostrar el diálogo de autorización de Meta y la cuenta
   profesional/Página elegida (ocultar identificadores personales innecesarios).
2. Mostrar el consentimiento de publicación `instagram_content_publish` y los permisos de cuenta/Página que
   requiera el flujo; aceptar con un activo de prueba autorizado.
3. Volver a ClipsAI y mostrar la cuenta conectada. Seleccionar un Reel/clip autorizado, revisar caption y
   opciones disponibles, y pulsar **Publicar**.
4. Mostrar el estado devuelto por ClipsAI y el Reel en la cuenta de prueba si ya está disponible; explicar o
   mostrar la desconexión de Instagram desde Integraciones.

### Grabación TikTok

1. Iniciar la conexión TikTok desde Integraciones; mostrar la cuenta y el diálogo de autorización con los
   permisos de identidad básica y publicación solicitados. Aceptar con una cuenta de prueba autorizada.
2. Volver a ClipsAI y mostrar la cuenta conectada. Seleccionar el clip propio, completar caption y opciones de
   audiencia/privacidad que presente la API, y pulsar **Publicar en TikTok**.
3. Mostrar carga, respuesta/estado de publicación y el video en la cuenta de prueba cuando el estado lo permita.
   Finalizar mostrando dónde desconectar TikTok.

Mantener los videos de prueba privados o retirarlos al terminar, salvo autorización expresa para hacerlos
públicos. Respetar los límites de formato/tamaño del formulario de revisión.

Nombre sugerido: `clipsai-oauth-youtube-review.mp4`, `clipsai-oauth-instagram-review.mp4` y
`clipsai-oauth-tiktok-review.mp4`. Revisar límites de tamaño/formato del formulario de cada consola.

## 6. Variables y verificación local

`.env.example` documenta nombres, callbacks, URLs públicas y scopes sin credenciales. Valores esperados:

| Proveedor | Variables de backend | Scope de publicación |
| --- | --- | --- |
| Google / YouTube | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | `youtube.upload` (el servicio también pide `youtube.readonly`) |
| Meta / Instagram | `INSTAGRAM_CLIENT_ID`, `INSTAGRAM_CLIENT_SECRET`, `INSTAGRAM_REDIRECT_URI` | `instagram_content_publish` (el servicio pide scopes de cuenta/página adicionales) |
| TikTok | `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`, `TIKTOK_SCOPES` | `video.publish` (también `video.upload` y `user.info.basic`) |

Comprobaciones tras despliegue:

- [ ] Variables del despliegue coinciden con callbacks permitidos en consola y utilizan HTTPS; frontend
  apunta al API público y las redirecciones vuelven a `https://clipsai.xyz`.
- [ ] `GET` de landing y páginas legales retorna página pública; `/sitemap.xml` y `/robots.txt` son accesibles.
- [ ] OAuth de cada proveedor completa ida/vuelta, scope aprobado, cuenta conectada, publicación iniciada por
  el usuario, estado de resultado, desconexión y revocación.
- [ ] La eliminación elimina datos/tokens locales de acuerdo con el proceso publicado. Verificar aparte qué
  datos o publicaciones permanecen en cada red social.
- [ ] No hay tokens ni credenciales en logs, bundles del frontend, repositorio ni evidencia de revisión.

## 7. Estado del repositorio y pendientes externos

### Listo o verificable en el repositorio

- [x] Las rutas públicas legales están registradas en `frontend_react/src/App.tsx` y los enlaces se muestran
  en el footer de la landing (`frontend_common/components/landing/landingData.ts`).
- [x] `frontend_common/public/sitemap.xml` enumera la landing y las tres URLs legales con HTTPS; el XML se
  valida localmente. `robots.txt` referencia el sitemap.
- [x] Hay favicon SVG y recurso Open Graph de marca en `frontend_common/public/`.
- [x] El código define los scopes/callbacks que documenta esta guía; `.env.example` lista nombres de variables,
  dominios y URLs legales sin credenciales reales.
- [x] Existen los guiones de grabación y los pasos/checklists para las tres consolas en este documento.

### Pendiente manual / no verificable solo desde el repositorio

- [ ] Desplegar `https://clipsai.xyz` y `https://api.clipsai.xyz`, comprobar certificados, DNS, HTTPS, rutas SPA,
  accesibilidad anónima y URLs legales desde Internet.
- [ ] Confirmar que el gestor de secretos tiene credenciales de producción y `VAULT_KEY` fuerte/persistente; el
  `.env.example` no contiene secretos y no los provisiona.
- [ ] Obtener aprobación real y estado correcto en cada consola: Google OAuth/`youtube.upload`, Meta Live/
  `instagram_content_publish`, TikTok dominio verificado/`video.publish` auditado.
- [ ] Grabar, revisar y adjuntar los tres videos al formulario de cada proveedor.
- [ ] Ejecutar en despliegue pruebas reales de OAuth, publicación, revocación y eliminación, y conservar capturas
  o IDs de revisión como evidencia.

No marcar como aprobados los criterios de proveedores hasta contar con evidencia de consola. Registrar aquí el
resultado/evidencia de cada acción externa al completarla:

| Criterio | Evidencia a registrar | Estado |
| --- | --- | --- |
| Google OAuth verificado y `youtube.upload` aprobado | URL/ID de revisión, captura de estado aprobado | Pendiente de consola |
| Meta Live y `instagram_content_publish` aprobado | Captura de modo Live y permisos aprobados | Pendiente de consola |
| TikTok `video.publish` auditado y dominio verificado | Capturas/estado final de auditoría y dominio | Pendiente de consola |
| Conectar → publicar grabado por proveedor | Tres archivos de video revisados y adjuntos | Pendiente de grabación |
| Dominio HTTPS y enlaces legales públicos | Comprobación externa de URLs/certificado | Pendiente de despliegue |
| Variables de producción documentadas | `.env.example` y gestor de secretos configurado | Documentado; secretos/despliegue pendientes |
