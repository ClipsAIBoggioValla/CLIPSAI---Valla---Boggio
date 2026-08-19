# PROYECTO.md — clipsai: Sistema Web de Generación Automática de Clips Virales

## 1. Objetivo Principal

Convertir **clipsai** (motor de generación automática de clips virales a partir de video largo) en un sistema web completo: los usuarios suben un video, el sistema lo procesa de forma asíncrona con el pipeline existente (detección por audio + IA + FFmpeg) y les permite gestionar los clips generados a través de una API con autenticación y una interfaz web, soportando distintos tipos de contenido (opinión/just chatting, gaming, podcast multi-cámara).

La lógica de detección y edición ya validada por el motor **no se modifica** — el trabajo consiste en envolverla en una capa de persistencia, API y frontend, y en terminar de sumar los tipos de contenido que aún faltan (gaming y podcast).

## 2. Límites del Sistema

**✅ Dentro del alcance:**
- Pipeline de detección de momentos virales (análisis de audio + IA sobre transcripción) para video ya grabado
- Generación de clips en formato vertical (1080x1920), listos para publicar
- Tres tipos de contenido soportados: opinión/just chatting, gaming, podcast con conmutación de cámara entre 2 personas
- Gestión de usuarios, videos, jobs de procesamiento y clips generados, vía API con autenticación
- Interfaz web para subir video, seguir el progreso del procesamiento y gestionar (listar/editar/borrar/descargar) los clips generados
- Persistencia de todo lo anterior en base de datos relacional dockerizada
- Backend implementado en 2 frameworks con paridad de endpoints; frontend implementado en 2 frameworks con paridad de vistas y flujo

**❌ Fuera del alcance:**
- Procesamiento de streams en vivo / tiempo real
- Publicación automática a redes sociales (el usuario descarga el clip y lo sube manualmente)
- Aplicación móvil nativa
- Edición manual de clips dentro del sistema (cortar, reordenar, retocar a mano) — el sistema solo genera, el usuario descarga
- Subtitulado o doblaje a otros idiomas fuera del español rioplatense
- Notificaciones push o por email
- Arquitectura distribuida / escalado multi-servidor (corre en un solo host, vía `docker-compose`)

## 3. Alcances Funcionales

- Registro e inicio de sesión con JWT
- Subida de video, con selección de tipo de contenido (opinión, gaming, podcast) y preset de calidad (viral / natural / cinemático), acompañada de la transcripción del video (el sistema sigue requiriéndola como input, no la genera de forma transparente)
- Disparo asíncrono del análisis (creación de un `Job`) con consulta de estado (`pendiente` → `procesando` → `completado` / `error`)
- Detección de momentos por análisis de audio (RMS, eventos) combinada con IA sobre la transcripción — lógica ya existente, sin cambios
- **Subtitulado automático**: generación de subtítulos quemados (burned-in) sobre cada clip, sincronizados con la transcripción ya generada por el pipeline
- **Generación de hook**: selección/armado de un segmento inicial (primeros segundos) pensado para enganchar al espectador antes de dar paso al resto del clip
- **Compositor de podcast**: conmutación de cámara/plano entre 2 personas ubicadas en distintas partes del video, según quién esté hablando — a terminar
- *(Prioridad baja / opcional si el tiempo lo permite)* Compositor de gaming: composición y formato específico para contenido de videojuegos
- CRUD completo sobre `Clip` (listar, editar metadata como título/tags, eliminar)
- Listado y filtro de clips por video, tipo de contenido y estado
- Descarga de clips generados desde el frontend

## 4. Alcances No Funcionales

- **Seguridad**: contraseñas hasheadas (bcrypt o similar), autenticación JWT, sin API keys ni secretos hardcodeados en el repositorio (uso de variables de entorno)
- **Persistencia**: PostgreSQL dockerizada, con volumen para no perder datos entre reinicios
- **Disponibilidad**: el procesamiento es asíncrono y no bloqueante; tiempos de procesamiento largos (varios minutos) son aceptables y esperados
- **Mantenibilidad**: paridad de comportamiento verificable entre ambos backends y ambos frontends; motor de clipsai desacoplado de la capa web mediante una interfaz estable (input: video + parámetros de contenido/preset; output: job con estado + clips generados)
- **Desplegabilidad**: `docker-compose up` levanta la base de datos junto con al menos un backend y un frontend en menos de 2 minutos

## 5. Objetivos Específicos y Medibles

1. Implementar 2 backends (FastAPI y Express) con paridad 100% de endpoints sobre las entidades `Usuario`, `Video`, `Job` y `Clip`
2. Implementar 2 frontends (React y Vue) con las mismas vistas: login, subida de video, seguimiento de jobs, listado/edición/borrado de clips
3. Implementar el subtitulado automático (burned-in) sobre los clips generados
4. Implementar la generación de un hook inicial en cada clip
5. Terminar e integrar el compositor de podcast (conmutación de cámara entre 2 personas) al flujo de `Job`
6. Mantener intacta la lógica de detección ya validada (`audio_analyzer.py`, `whisper_transcriber.py`, prompt de IA) mientras se construye la capa web en paralelo, sin romper el contrato motor↔API
7. Documentar la API con OpenAPI/Swagger en ambos backends
8. Eliminar cualquier secreto hardcodeado del código y migrarlo a variables de entorno antes de la entrega
9. *(Opcional, si el tiempo lo permite)* Terminar e integrar el compositor de gaming al flujo de `Job`
