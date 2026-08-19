# Diseño de Issues — clipsai (Trabajo Final Programación 3)

Orden de ejecución sugerido según dependencias. Cada una arranca en una rama propia desde `main` (`tipo/nombre-issue`), con commits en formato Conventional Commits, y termina en un PR hacia `main`.

---

## Issue 1 — Infraestructura: DB dockerizada y esquema inicial

**Descripción:** Levantar PostgreSQL vía Docker con volumen persistente y crear el esquema inicial de tablas.

**Objetivo:** Tener una base de datos funcional y persistente para que el resto del sistema (backends) puedan apoyarse en ella.

**Alcance incluido:** `docker-compose.yml` con servicio de Postgres + volumen; script/migración con tablas `usuarios`, `videos`, `jobs`, `clips` (con campos para estado de publicación y red social) y sus relaciones (FKs).
**Alcance excluido:** Lógica de negocio, endpoints, seeds de datos de prueba más allá de lo mínimo para verificar.

**Dependencias:** Ninguna.

**Criterios de aceptación:**
- `docker-compose up` levanta Postgres con datos persistidos entre reinicios (probado bajando y subiendo el contenedor)
- Las tablas existen con sus relaciones correctas (FK Job→Video, FK Clip→Job, FK Video→Usuario)

**Evidencias:** captura de `\dt` + `\d` de cada tabla en `psql`, captura de datos sobreviviendo un `docker-compose down && up`.

---

## Issue 2 — Contrato estable del motor de clipsai

**Descripción:** Envolver el pipeline actual (`main.py` y módulos asociados) en una interfaz clara y estable — sin tocar su lógica interna —, eliminando selecciones de tipos de contenido o presets innecesarios.

**Objetivo:** Desacoplar el motor de la capa web utilizando el flujo de video estandarizado que ya funciona correctamente.

**Alcance incluido:** Función/módulo invocable (o wrapper por subprocess) con la firma simplificada `(video, transcripcion)`; manejo de errores devueltos de forma estructurada.
**Alcance excluido:** Detección de tipos de contenido (podcast, gaming) o lógica multi-cámara.

**Dependencias:** Ninguna (puede ir en paralelo con la Issue 1).

**Criterios de aceptación:**
- Se puede invocar el motor desde un único punto de entrada pasando únicamente el video y su transcripción
- Un error interno del pipeline se devuelve como resultado estructurado (no un crash sin info)

**Evidencias:** ejemplo de invocación con salida (input/output) documentado en el PR.

---

## Issue 3 — Backend #1 (FastAPI): autenticación

**Descripción:** Registro y login de usuarios con JWT.

**Objetivo:** Que el sistema tenga usuarios identificables antes de exponer cualquier recurso.

**Alcance incluido:** `POST /auth/registro`, `POST /auth/login`, hash de contraseñas (bcrypt), emisión y validación de JWT, middleware de auth para proteger rutas.
**Alcance excluido:** Recuperación de contraseña, roles/permisos diferenciados.

**Dependencias:** Issue 1.

**Criterios de aceptación:**
- Un usuario se registra, loguea y recibe un JWT válido
- Una ruta protegida rechaza requests sin token o con token inválido (401)

**Evidencias:** colección de Postman/Thunder Client con los 3 casos (registro, login, ruta protegida sin/con token).

---

## Issue 4 — Backend #1 (FastAPI): subida de video y disparo de Job

**Descripción:** Endpoint para subir un video y disparar el análisis de forma asíncrona contra el motor (Issue 2).

**Objetivo:** Que un usuario autenticado pueda iniciar el procesamiento de un video sin bloquear el request.

**Alcance incluido:** `POST /videos` (sube archivo de video junto con su transcripción, valida formato/tamaño de ambos), `POST /videos/{id}/jobs` (crea Job en estado `pendiente`, dispara procesamiento en background), `GET /jobs/{id}` (consulta estado).
**Alcance excluido:** Cancelación de jobs en curso, reintentos automáticos.

**Dependencias:** Issue 1, Issue 2, Issue 3.

**Criterios de aceptación:**
- Subir un video no bloquea el request (responde antes de que termine el procesamiento)
- El estado del Job pasa correctamente por `pendiente` → `procesando` → `completado`/`error`
- Un archivo con formato inválido o sin su transcripción es rechazado con un mensaje claro

**Evidencias:** captura de polling a `GET /jobs/{id}` mostrando el cambio de estado en el tiempo.

---

## Issue 5 — Backend #1 (FastAPI): CRUD de Clips

**Descripción:** Endpoints para listar, editar y eliminar los clips generados por un Job completado.

**Objetivo:** Completar el CRUD que pide la consigna sobre la entidad Clip.

**Alcance incluido:** `GET /clips` (con filtro por video/estado), `PATCH /clips/{id}` (título, tags), `DELETE /clips/{id}`, `GET /clips/{id}/descarga`.
**Alcance excluido:** Edición del contenido del video en sí (recorte manual).

**Dependencias:** Issue 4.

**Criterios de aceptación:**
- CRUD completo probado: crear (vía Job), listar, editar metadata, eliminar
- Un usuario no puede ver/editar clips de otro usuario (403)

**Evidencias:** colección de requests cubriendo cada operación + caso de acceso denegado entre usuarios.

---

## Issue 6 — Backend #2 (Express): paridad completa con FastAPI

**Descripción:** Reimplementar exactamente los mismos endpoints, misma lógica y mismos contratos de entrada/salida que el backend FastAPI, contra la misma base de datos.

**Objetivo:** Cumplir el requisito de diversidad de frameworks con paridad 100%.

**Alcance incluido:** Todos los endpoints de las Issues 3, 4 y 5 reimplementados en Express, invocando el motor (Issue 2) vía subprocess o llamada HTTP interna.
**Alcance excluido:** Ninguna funcionalidad nueva que no exista ya en el backend FastAPI.

**Dependencias:** Issue 3, Issue 4, Issue 5.

**Criterios de aceptación:**
- Cada endpoint devuelve exactamente la misma forma de respuesta que su equivalente en FastAPI
- Un mismo usuario/token puede operar indistintamente contra cualquiera de los dos backends

**Evidencias:** tabla comparativa endpoint por endpoint con captura de respuesta de ambos backends ante el mismo request.

---

## Issue 7 — Frontend #1 (React): auth, subida y seguimiento de Jobs

**Descripción:** Vistas de login/registro, subida de video (video + transcripción) y pantalla de seguimiento de estado del Job.

**Objetivo:** Cubrir el flujo de entrada del usuario al sistema.

**Alcance incluido:** Formularios de auth, formulario de subida simplificado (video + transcripción), vista de progreso con polling y feedback visual del estado.
**Alcance excluido:** Selección de tipos de contenido (podcast/gaming) — el formulario es único y simplificado.

**Dependencias:** Issue 3, Issue 4.

**Criterios de aceptación:**
- Un usuario puede registrarse, loguearse, subir un video y ver el estado de su Job actualizarse sin recargar la página
- Errores de validación se muestran claramente en la UI

**Evidencias:** grabación corta o capturas del flujo completo.

---

## Issue 8 — Frontend #1 (React): gestión y publicación de Clips

**Descripción:** Vista de listado de clips con filtros, edición de metadata, borrado, descarga y acción de publicación automática a redes sociales.

**Objetivo:** Completar el flujo de CRUD y la integración social del lado del usuario.

**Alcance incluido:** Listado con filtros, edición inline o modal, confirmación de borrado, botón de descarga y botón/modal de "Publicar en Redes".
**Alcance excluido:** Reproductor avanzado o editor multi-pista dentro del navegador.

**Dependencias:** Issue 5, Issue 7.

**Criterios de aceptación:**
- Listar, editar, borrar y gatillar la publicación de un clip funciona de punta a punta contra el backend

**Evidencias:** capturas del listado antes/después de editar, borrar o publicar un clip.

---

## Issue 9 — Frontend #2 (Vue): paridad completa con React

**Descripción:** Reimplementar las mismas vistas y flujo que el frontend React, consumiendo cualquiera de los dos backends.

**Objetivo:** Cumplir el requisito de diversidad de frameworks en el frontend.

**Alcance incluido:** Todas las vistas de las Issues 7 y 8 reimplementadas en Vue.
**Alcance excluido:** Cualquier vista o funcionalidad no presente en el frontend React.

**Dependencias:** Issue 7, Issue 8.

**Criterios de aceptación:**
- Mismo flujo de usuario, mismas vistas, mismo resultado visible que en React, contra el mismo backend

**Evidencias:** capturas lado a lado de cada vista equivalente en React y Vue.

---

## Issue 10 — Feature: subtitulado automático (burned-in)

**Descripción:** Generar subtítulos quemados sobre cada clip usando los timestamps palabra por palabra que produce el transcriptor.

**Objetivo:** Mejorar la retención y la calidad visual de los clips sin requerir edición manual del usuario.

**Alcance incluido:** Integración al motor (Issue 2) mediante FFmpeg / MoviePy para incrustar subtítulos legibles y sincronizados con el audio; el archivo resultante queda referenciado en la metadata del Clip.
**Alcance excluido:** Subtítulos editables por el usuario desde el frontend, traducción a otros idiomas.

**Dependencias:** Issue 2, Issue 5.

**Criterios de aceptación:**
- Cada clip generado incluye subtítulos dinámicos, legibles y sincronizados con el audio

**Evidencias:** clip de ejemplo (o capturas de frames) mostrando los subtítulos quemados.

---

## Issue 11 — Feature: generación de hook inicial

**Descripción:** Detectar y anteponer un segmento corto de alta energía al inicio de cada clip, pensado para enganchar al espectador antes de continuar con el resto del contenido.

**Objetivo:** Aumentar el potencial de retención/viralidad de los clips en redes de formato vertical.

**Alcance incluido:** Lógica en el motor que, reutilizando el scoring de `audio_analyzer` y la transcripción, identifique el fragmento con mayor "gancho" dentro del clip y lo anteponga al inicio.
**Alcance excluido:** Generación de contenido sintético (voces o imágenes generadas por IA).

**Dependencias:** Issue 2.

**Criterios de aceptación:**
- El clip generado arranca con el segmento identificado como hook
- El fragmento del hook demuestra un nivel de energía/score superior al promedio del clip

**Evidencias:** comparación de un clip con y sin la feature activada, mostrando el score del segmento elegido como hook.

---

## Issue 12 — Feature: subida automática a redes sociales

**Descripción:** Módulo de integración para publicar directamente clips generados en plataformas de formato vertical (ej. TikTok, Instagram Reels, YouTube Shorts) mediante sus APIs oficiales o un servicio/webhook de automatización.

**Objetivo:** Permitir que el usuario dispare o programe la publicación automática de un clip desde la plataforma.

**Alcance incluido:** Endpoint `POST /clips/{id}/publicar` (recibe plataforma destino y metadata opcional), ejecución asíncrona de la subida y actualización del estado del clip a `publicado` guardando la URL/ID devuelta por la red social.
**Alcance excluido:** Programación con calendario multicuenta avanzado.

**Dependencias:** Issue 5, Issue 10, Issue 11.

**Criterios de aceptación:**
- Invocar el endpoint de publicación envía el clip a la red seleccionada y registra la respuesta/link exitoso
- La UI refleja el cambio de estado del clip a `publicado`

**Evidencias:** logs del backend confirmando la llamada exitosa a la API externa y URL/ID de la publicación obtenida.

---

## Issue 13 — Seguridad y empaquetado final

**Descripción:** Eliminar cualquier secreto hardcodeado del código (incluida la API key ya detectada en `main.py`), migrar todo a variables de entorno, y completar el `docker-compose.yml` para levantar el sistema completo.

**Objetivo:** Dejar el sistema en condiciones seguras y desplegables para la entrega final.

**Alcance incluido:** `.env.example`, revisión de todo el código en busca de secretos, `docker-compose.yml` final con DB + backends + frontends.
**Alcance excluido:** Configuración de CI/CD, despliegue a un servidor externo.

**Dependencias:** Issue 6, Issue 9, Issue 12.

**Criterios de aceptación:**
- `git grep` por patrones de API keys no encuentra nada hardcodeado
- `docker-compose up` levanta el sistema completo en menos de 2 minutos

**Evidencias:** resultado del `git grep`, captura del sistema completo funcionando desde cero.

---

## Issue 14 — Documentación de API (OpenAPI/Swagger)

**Descripción:** Documentar ambos backends con OpenAPI/Swagger.

**Objetivo:** Cumplir el objetivo de documentación medible del trabajo final.

**Alcance incluido:** Spec OpenAPI generada/mantenida para FastAPI y Express, accesible vía `/docs` o `/api-docs` en ambos backends.
**Alcance excluido:** Generación de SDK cliente automático.

**Dependencias:** Issue 6, Issue 12.

**Criterios de aceptación:**
- Ambos backends exponen su documentación interactiva actualizada con los nuevos endpoints de publicación

**Evidencias:** capturas de `/docs` de ambos backends.
