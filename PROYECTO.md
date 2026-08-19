# PROYECTO.md — clipsai: Sistema Web de Generación Automática de Clips Virales y Publicación Automática

## 1. Objetivo Principal

Convertir **clipsai** (motor de generación automática de clips virales a partir de video largo) en un sistema web completo: los usuarios suben un video, el sistema lo procesa de forma asíncrona con el pipeline existente (detección por audio + IA + FFmpeg), le añade **subtítulos quemados dinámicos**, antepone un **hook inicial de alta energía**, y permite gestionar y **publicar automáticamente los clips generados en redes sociales** a través de una API con autenticación y una interfaz web.

Se simplifica el alcance eliminando múltiples tipos de contenido (podcast multi-cámara, gaming) para enfocarse al 100% en el formato único de video que ya funciona de forma estable y probada.

## 2. Límites del Sistema

**✅ Dentro del alcance:**
- Pipeline de detección de momentos virales (análisis de audio + IA sobre transcripción) sobre el formato de video principal estandarizado
- Generación de clips en formato vertical (1080x1920), listos para publicar
- **Subtitulado automático dinámico (burned-in)** en cada clip
- **Generación de hook inicial** mediante selección del segmento de mayor impacto/energía
- **Publicación automática a redes sociales** (TikTok, Instagram Reels, YouTube Shorts) mediante endpoints dedicados o webhooks de integración
- Gestión de usuarios, videos, jobs de procesamiento y clips generados, vía API con autenticación
- Interfaz web para subir video, seguir el progreso del procesamiento, gestionar los clips (listar/editar/borrar/descargar) y gatillar su publicación
- Persistencia de todo lo anterior en base de datos relacional dockerizada
- Backend implementado en 2 frameworks con paridad de endpoints (FastAPI y Express); frontend implementado en 2 frameworks con paridad de vistas y flujo (React y Vue)

**❌ Fuera del alcance:**
- Procesamiento de streams en vivo / tiempo real
- Compositor multi-cámara para podcast (conmutación de planos entre hablantes)
- Compositor específico para gaming (layout pantalla dividida streamer/gameplay)
- Aplicación móvil nativa
- Edición manual de clips dentro del sistema (cortar, reordenar, retocar a mano el video)
- Subtitulado o doblaje a otros idiomas fuera del español
- Arquitectura distribuida / escalado multi-servidor (corre en un solo host, vía `docker-compose`)

## 3. Alcances Funcionales

- Registro e inicio de sesión con JWT
- Subida de video acompañada de su transcripción (el sistema la requiere como input)
- Disparo asíncrono del análisis (creación de un `Job`) con consulta de estado (`pendiente` → `procesando` → `completado` / `error`)
- Detección de momentos por análisis de audio (RMS, eventos) combinada con IA sobre la transcripción
- **Subtitulado automático**: generación de subtítulos quemados (burned-in) dinámicos y legibles sobre cada clip, sincronizados palabra por palabra
- **Generación de hook inicial**: detección del fragmento de mayor score/energía y reordenamiento/anteposición al inicio del clip para maximizar retención
- **Publicación automática a redes sociales**: integración con API/servicio externo para subir clips directamente a TikTok, Instagram Reels o YouTube Shorts
- CRUD completo sobre `Clip` (listar, editar metadata como título/tags, eliminar)
- Listado y filtro de clips por video y estado (generado / publicado / error)
- Descarga y publicación directa de clips generados desde el frontend

## 4. Alcances No Funcionales

- **Seguridad**: contraseñas hasheadas (bcrypt), autenticación JWT, sin API keys ni secretos hardcodeados en el repositorio (uso estricto de variables de entorno)
- **Persistencia**: PostgreSQL dockerizada, con volumen para no perder datos entre reinicios
- **Disponibilidad**: procesamiento asíncrono y no bloqueante
- **Mantenibilidad**: paridad de comportamiento verificable entre ambos backends y ambos frontends; motor de clipsai desacoplado de la capa web mediante una interfaz estable (input: video + transcripción; output: job con estado + clips generados)
- **Desplegabilidad**: `docker-compose up` levanta la base de datos junto con backends y frontends en menos de 2 minutos

## 5. Objetivos Específicos y Medibles

1. Implementar 2 backends (FastAPI y Express) con paridad 100% de endpoints sobre las entidades `Usuario`, `Video`, `Job` y `Clip`
2. Implementar 2 frontends (React y Vue) con las mismas vistas: login, subida de video, seguimiento de jobs, listado/edición/borrado de clips y botón/modal de publicación automática a redes
3. Implementar la generación de subtítulos automáticos (burned-in) sincronizados en cada clip
4. Implementar la selección y anteposición automática de un hook inicial de alto impacto
5. Implementar el módulo y endpoint de publicación automática a redes sociales
6. Mantener intacta la lógica de detección ya validada mientras se construye la capa web y las nuevas features en paralelo
7. Documentar la API con OpenAPI/Swagger en ambos backends
8. Eliminar cualquier secreto hardcodeado del código y migrarlo a variables de entorno antes de la entrega
