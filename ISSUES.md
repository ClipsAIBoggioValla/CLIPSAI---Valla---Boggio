# Diseño de Issues — clipsai (Trabajo Final Programación 3)

Orden de ejecución sugerido según dependencias. Cada una arranca en una rama propia desde `main` (`tipo/nombre-issue`), con commits en formato Conventional Commits, y termina en un PR hacia `main`.

---

## Issue 1 — Infraestructura: DB dockerizada y esquema inicial

**Descripción:** Levantar PostgreSQL vía Docker con volumen persistente y crear el esquema inicial de tablas.

**Objetivo:** Tener una base de datos funcional y persistente para que el resto del sistema (backends) puedan apoyarse en ella.

**Alcance incluido:** `docker-compose.yml` con servicio de Postgres + volumen; script/migración con tablas `usuarios`, `videos`, `jobs`, `clips` y sus relaciones (FKs).
**Alcance excluido:** Lógica de negocio, endpoints, seeds de datos de prueba más allá de lo mínimo para verificar.

**Dependencias:** Ninguna.

**Criterios de aceptación:**
- `docker-compose up` levanta Postgres con datos persistidos entre reinicios (probado bajando y subiendo el contenedor)
- Las 4 tablas existen con sus relaciones correctas (FK Job→Video, FK Clip→Job, FK Video→Usuario)

**Evidencias:** captura de `\dt` + `\d` de cada tabla en `psql`, captura de datos sobreviviendo un `docker-compose down && up`.

---

## Issue 2 — Contrato estable del motor de clipsai

**Descripción:** Envolver el pipeline actual (`main.py` y módulos asociados) en una interfaz clara y estable — sin tocar su lógica interna — que reciba (video, tipo de contenido, preset) y devuelva (lista de clips con metadata: timestamps, score, ruta, estado).

**Objetivo:** Desacoplar el motor de la capa web para poder desarrollar ambos en paralelo sin que cambios internos del motor rompan la API.

**Alcance incluido:** Función/módulo invocable (o wrapper por subprocess) con esa firma fija; manejo de errores devueltos de forma estructurada (no solo prints).
**Alcance excluido:** Cambios a la lógica de detección, whisper, audio_analyzer o al prompt de IA.

**Dependencias:** Ninguna (puede ir en paralelo con la Issue 1).

**Criterios de aceptación:**
- Se puede invocar el motor con los 3 tipos de contenido existentes/planeados (opinión, podcast, gaming) desde un único punto de entrada
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

**Alcance incluido:** `POST /videos` (sube archivo de video **junto con su transcripción**, valida formato/tamaño de ambos), `POST /videos/{id}/jobs` (crea Job en estado `pendiente`, dispara procesamiento en background), `GET /jobs/{id}` (consulta estado).
**Alcance excluido:** Cancelación de jobs en curso, reintentos automáticos, generación automática de la transcripción dentro de este flujo (el sistema sigue recibiéndola como input del usuario).

**Dependencias:** Issue 1, Issue 2, Issue 3.

**Criterios de aceptación:**
- Subir un video no bloquea el request (responde antes de que termine el procesamiento)
- El estado del Job pasa correctamente por `pendiente` → `procesando` → `completado`/`error`
- Un archivo con formato inválido es rechazado con un mensaje claro
- Subir un video sin su transcripción es rechazado con un mensaje claro (la transcripción sigue siendo obligatoria)

**Evidencias:** captura de polling a `GET /jobs/{id}` mostrando el cambio de estado en el tiempo.

---

## Issue 5 — Backend #1 (FastAPI): CRUD de Clips

**Descripción:** Endpoints para listar, editar y eliminar los clips generados por un Job completado.

**Objetivo:** Completar el CRUD que pide la consigna sobre la entidad Clip.

**Alcance incluido:** `GET /clips` (con filtro por video/tipo de contenido/estado), `PATCH /clips/{id}` (título, tags), `DELETE /clips/{id}`, `GET /clips/{id}/descarga`.
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
- Cada endpoint devuelve exactamente la misma forma de respuesta que su equivalente en FastAPI (mismo JSON shape, mismos códigos de estado)
- Un mismo usuario/token puede operar indistintamente contra cualquiera de los dos backends

**Evidencias:** tabla comparativa endpoint por endpoint con captura de respuesta de ambos backends ante el mismo request.

---

## Issue 7 — Frontend #1 (React): auth, subida y seguimiento de Jobs

**Descripción:** Vistas de login/registro, subida de video (con selección de tipo de contenido y preset) y pantalla de seguimiento de estado del Job.

**Objetivo:** Cubrir el flujo de entrada del usuario al sistema.

**Alcance incluido:** Formularios de auth, formulario de subida (video + su transcripción), vista de progreso con polling y feedback visual del estado.
**Alcance excluido:** Gestión de clips (va en la Issue 8).

**Dependencias:** Issue 3, Issue 4.

**Criterios de aceptación:**
- Un usuario puede registrarse, loguearse, subir un video y ver el estado de su Job actualizarse sin recargar la página
- Errores de validación (ej. formato de archivo inválido) se muestran en la UI

**Evidencias:** grabación corta o capturas del flujo completo.

---

## Issue 8 — Frontend #1 (React): gestión de Clips

**Descripción:** Vista de listado de clips con filtros, edición de metadata, borrado y descarga.

**Objetivo:** Completar el flujo de CRUD del lado del usuario.

**Alcance incluido:** Listado con filtros, edición inline o modal, confirmación de borrado, botón de descarga.
**Alcance excluido:** Reproducción/edición de video dentro del navegador más allá de un preview básico.

**Dependencias:** Issue 5, Issue 7.

**Criterios de aceptación:**
- Listar, editar y borrar un clip funciona de punta a punta contra el backend
- El filtro por tipo de contenido/estado actualiza la lista correctamente

**Evidencias:** capturas del listado antes/después de editar y borrar un clip.

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

**Descripción:** Generar subtítulos quemados sobre cada clip usando los timestamps palabra por palabra que ya produce el transcriptor.

**Objetivo:** Mejorar la calidad de los clips generados sin depender de edición manual del usuario.

**Alcance incluido:** Integración al motor (Issue 2) para que cada Clip generado incluya versión con subtítulos quemados; el archivo resultante queda referenciado en la metadata del Clip.
**Alcance excluido:** Subtítulos editables por el usuario desde el frontend, traducción a otros idiomas.

**Dependencias:** Issue 2, Issue 5 (para exponer el resultado en la API).

**Criterios de aceptación:**
- Un clip generado incluye subtítulos legibles y sincronizados con el audio
- El estilo de subtítulo es consistente entre los 3 tipos de contenido

**Evidencias:** clip de ejemplo (o captura de frames) mostrando los subtítulos quemados.

---

## Issue 11 — Feature: generación de hook inicial

**Descripción:** Detectar y anteponer un segmento corto al inicio de cada clip, pensado para enganchar al espectador antes de continuar con el resto del contenido.

**Objetivo:** Aumentar el potencial de retención/viralidad de los clips generados.

**Alcance incluido:** Lógica que, reutilizando el scoring de momentos ya existente, identifique el fragmento con mayor potencial de "gancho" dentro del clip y lo reordene/anteponga.
**Alcance excluido:** Generación de hooks con contenido sintético (texto/voz generada) — el hook sale de material ya existente en el video.

**Dependencias:** Issue 2.

**Criterios de aceptación:**
- Cada clip generado arranca con el segmento identificado como hook, no con el inicio cronológico original
- El hook es notablemente distinto (más alta energía/score) que el promedio del resto del clip, verificable con los datos de `audio_analyzer`

**Evidencias:** comparación de un clip con y sin la feature activada, mostrando el score del segmento elegido como hook.

---

## Issue 12 — Feature: compositor de podcast (multi-cámara)

**Descripción:** Conmutación de cámara/plano entre 2 personas ubicadas en distintas partes del video, según quién esté hablando.

**Objetivo:** Soportar el tipo de contenido "podcast" de forma completa, no solo como transcripción/detección genérica.

**Alcance incluido:** Detección de quién habla (por audio o por posición ya conocida de cada persona en el frame), recorte/composición dinámica siguiendo al hablante activo.
**Alcance excluido:** Detección facial/reconocimiento de identidad; se asume una disposición conocida de las 2 cámaras/posiciones.

**Dependencias:** Issue 2.

**Criterios de aceptación:**
- Un video de podcast de prueba con 2 personas genera un clip que conmuta correctamente el encuadre según quién habla
- No hay saltos de cámara mientras la misma persona sigue hablando

**Evidencias:** clip de ejemplo mostrando al menos 2 conmutaciones de cámara correctas.

---

## Issue 13 — (Opcional) Feature: compositor de gaming

**Descripción:** Composición y formato específico para contenido de videojuegos.

**Objetivo:** Sumar el tercer tipo de contenido si el tiempo del proyecto lo permite.

**Alcance incluido:** Composición vertical adaptada a gameplay + cámara del streamer (si aplica).
**Alcance excluido:** Todo lo que no sea la composición del formato — la detección de momentos virales ya es genérica.

**Dependencias:** Issue 2.

**Criterios de aceptación:**
- Un video de gaming de prueba genera un clip con la composición esperada

**Evidencias:** clip de ejemplo.

---

## Issue 14 — Seguridad y empaquetado final

**Descripción:** Eliminar cualquier secreto hardcodeado del código (incluida la API key ya detectada en `main.py`), migrar todo a variables de entorno, y completar el `docker-compose.yml` para levantar el sistema completo.

**Objetivo:** Dejar el sistema en condiciones seguras y desplegables para la entrega.

**Alcance incluido:** `.env.example`, revisión de todo el código en busca de secretos, `docker-compose.yml` final con DB + backends + frontends.
**Alcance excluido:** Configuración de CI/CD, despliegue a un servidor externo.

**Dependencias:** Issue 6, Issue 9.

**Criterios de aceptación:**
- `git grep` por patrones de API keys no encuentra nada hardcodeado
- `docker-compose up` levanta el sistema completo en menos de 2 minutos

**Evidencias:** resultado del `git grep`, captura del sistema completo funcionando desde cero.

---

## Issue 15 — Documentación de API (OpenAPI/Swagger)

**Descripción:** Documentar ambos backends con OpenAPI/Swagger.

**Objetivo:** Cumplir el objetivo de documentación medible del trabajo final.

**Alcance incluido:** Spec OpenAPI generada/mantenida para FastAPI y Express, accesible vía `/docs` o similar en ambos.
**Alcance excluido:** Generación de SDK cliente automático.

**Dependencias:** Issue 6.

**Criterios de aceptación:**
- Ambos backends exponen su documentación interactiva y coincide con los endpoints reales

**Evidencias:** capturas de `/docs` de ambos backends.
