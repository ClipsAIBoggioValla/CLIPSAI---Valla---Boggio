<!-- evaluacion:inicio -->
# Evaluación — ClipsAIBoggioValla/CLIPSAI---Valla---Boggio

> Documento **generado automáticamente** por la cátedra de Programación III (RepoSense + análisis de calidad + constancia). **No editar a mano**: se regenera en cada evaluación.
> Rama evaluada: `main`. Análisis **heurístico** (regex + métricas): es una criba para orientar la revisión, **no una nota**.
> Generado: 2026-11-02.

## 1. Veredicto

| Aspecto | Resultado |
|---|---|
| Tipo de proyecto | frontend |
| Índice de calidad de servicios | **2/100** (mínimo 60) |
| Criterios cumplidos | **9/15** |
| Aprobado (semáforo) | **NO** |
| Código (LOC) | 26,232 |
| Archivos de código | 249 |
| Tests (archivos) | 6 |
| Cobertura de líneas | 21.3% (mínimo 80%) |
| Capas detectadas | vistas, servicios, estado |

> **Aprobado** exige cumplir **todos** los criterios del semáforo. No es una nota: sirve para ordenar y priorizar la revisión.

## 2. Autoría (RepoSense)

| Autor | Commits | Código (LOC) | Tests (LOC) | Docs (LOC) | Días activos | % del código |
|---|---:|---:|---:|---:|---:|---:|
| mateo | 64 | 20,067 | 422 | 1,489 | 33 | 66% |
| SantiValla | 39 | 10,144 | 45 | 600 | 13 | 34% |

> _El LOC de autoría lo calcula RepoSense sobre el historial y puede diferir del LOC de código del análisis de calidad (que mira solo el estado de `main`)._

> **Reparto del trabajo:** mateo concentra el 66% de las líneas de código. Un reparto muy desigual suele indicar que la integración no fue realmente en equipo; vale la pena reconstruir cómo se coordinó.

## 3. Constancia (IC) — todas las ramas

> El IC mide **cuándo** se trabajó (sesiones por semana, pausas y recencia), no cuánto ni con qué calidad. Se calcula sobre **todas las ramas** de todos los repositorios del alumno, no sólo `main`.

| Alumno | Sesiones | Cumplimiento | Pausa | Recencia | IC | Nivel | Para subir de nivel |
|---|--:|--:|--:|--:|--:|--|--|
| mateo | 30 | 100% | 12 d | 93% | **78** | No aprueba | Pausa 12 d (máx. 10 d) |
| SantiValla | 14 | 64% | 19 d | 93% | **54** | No aprueba | Pausa 19 d (máx. 10 d) |

> Para aprobar el IC: **2 sesiones por semana** sostenidas, sin pausas mayores a **10 días** y con actividad en las **últimas 2 semanas**. Se excluyen merges, bots y al docente. Zona horaria UTC-3.

## 4. Aspectos evaluados

Cada aspecto indica **qué mide**, **por qué importa** y **tu resultado**. Cuando el resultado está en rojo, se agregan preguntas para **investigar la causa** (no hay recetas: entender el porqué es parte de la evaluación).

### 1. Índice de calidad de servicios (indice) — A REVISAR

- **Qué mide:** Un resumen numérico (0-100) que combina todas las señales y métricas del análisis, con topes duros por duplicación.
- **Por qué importa:** Ordena y prioriza la revisión: un índice bajo indica varias señales que conviene mirar juntas.
- **Tu resultado:** índice **2/100** _(mínimo 60)_
- **Para investigar la causa:**
    - ¿En qué momento del proyecto se concentraron los problemas (arranque, integración de partes, cierre)?
    - ¿El índice bajó por muchas señales chicas o por una o dos graves?
    - ¿Se revisó el código integrado después de unir el trabajo de cada integrante?

### 2. Duplicación (DRY) (duplicacion) — OK

- **Qué mide:** Porcentaje de bloques de código repetidos (similitud) en el repositorio.
- **Por qué importa:** Cada copia se mantiene por separado: un arreglo hay que repetirlo y los defectos se multiplican.
- **Tu resultado:** **10.2%** de duplicación _(máximo 15%)_

### 3. Secretos hardcodeados (SEC) — A REVISAR

- **Qué mide:** Credenciales, tokens o claves escritos directamente en el código en vez de leerse de variables de entorno.
- **Por qué importa:** Un secreto en el repositorio queda expuesto en el historial aunque luego se borre, y compromete al servicio y a sus usuarios.
- **Tu resultado:** **7** secreto(s) hardcodeado(s) _(máximo 0)_
- **Para investigar la causa:**
    - ¿De dónde salió ese valor: un ejemplo, una prueba rápida, una copia de un compañero?
    - ¿En qué momento entró al código y por qué no se sacó antes de cerrar la tarea?
    - ¿Se acordó cómo manejar credenciales antes de empezar, o se postergó para el final?

### 4. Consultas SQL por concatenación (SQL) — OK

- **Qué mide:** Consultas SQL armadas concatenando o interpolando valores en vez de usar parámetros.
- **Por qué importa:** Es la puerta clásica a inyección: un valor que llega de afuera puede cambiar la consulta.
- **Tu resultado:** **0** consulta(s) SQL por concatenación _(máximo 0)_

### 5. Separación en capas (capas) — OK

- **Qué mide:** Si el código está separado en capas reconocibles (backend: presentación / lógica / datos; frontend: vistas / servicios / estado).
- **Por qué importa:** Sin separación, cada archivo hace de todo y cualquier cambio toca varios lugares a la vez.
- **Tu resultado:** **3** capa(s) detectada(s): vistas, servicios, estado _(mínimo 2 capas (a partir de 150 LOC))_

### 6. Acceso a datos dentro del componente (HTTP) — OK

- **Qué mide:** Llamadas `fetch`/`axios` dentro de componentes de UI en vez de una capa de servicios/API.
- **Por qué importa:** Duplica la lógica de acceso a datos y acopla la vista al backend: un cambio de API toca muchos componentes.
- **Tu resultado:** **0** llamada(s) a la API dentro de componente(s) _(máximo 0)_

### 7. Depuración olvidada (DBG) — A REVISAR

- **Qué mide:** Mensajes de depuración olvidados (`console.log`, `print`, `debugger`).
- **Por qué importa:** Generan ruido en los registros, pueden filtrar datos y dan sensación de código sin terminar.
- **Tu resultado:** **55** mensaje(s) de depuración olvidado(s) _(máximo 0)_
- **Para investigar la causa:**
    - ¿Fue depuración que quedó al cerrar una tarea, o se usó como registro permanente?
    - ¿Hubo una revisión final antes de cerrar la issue o la entrega?
    - ¿Quién agregó cada mensaje y con qué objetivo?

### 8. Uso del tipo `any` (Any) — OK

- **Qué mide:** Uso de `any` en TypeScript, que desactiva la verificación de tipos.
- **Por qué importa:** Se pierde la ayuda del compilador justo donde los datos vienen de afuera (API, formularios).
- **Tu resultado:** **1** uso(s) de `any` _(máximo 2)_

### 9. Componente demasiado grande (BigC) — OK

- **Qué mide:** Componentes de UI muy extensos, que suelen mezclar render, estado y lógica.
- **Por qué importa:** Son difíciles de leer, probar y reutilizar, y sus cambios tienen efectos inesperados.
- **Tu resultado:** **1** componente(s) demasiado grande(s) _(máximo 1)_

### 10. Baja cohesión (Coh) — A REVISAR

- **Qué mide:** Una clase o unidad cuyos métodos y campos no están relacionados entre sí.
- **Por qué importa:** Una unidad que cambia por motivos distintos es frágil y cuesta entenderla.
- **Tu resultado:** **1** unidad(es) con baja cohesión _(máximo 0)_
- **Para investigar la causa:**
    - ¿La unidad agrupa cosas que en realidad pertenecen a lugares distintos?
    - ¿Cambia por motivos diferentes según la tarea?
    - ¿Se pensó su responsabilidad antes de escribirla, o se fue agregando?

### 11. Complejidad alta (Compl) — A REVISAR

- **Qué mide:** Complejidad ciclomática: cantidad de caminos posibles dentro de una función (condicionales, bucles, casos).
- **Por qué importa:** Muchos caminos = difícil de seguir y de probar; suelen esconderse casos sin cubrir.
- **Tu resultado:** **279** bloque(s) de complejidad alta _(máximo 5 por 1000 LOC (tenés 26232 LOC))_
- **Para investigar la causa:**
    - ¿Se agregaron condiciones a medida que aparecían casos nuevos?
    - ¿Se probaron todos los caminos o solo el caso principal?
    - ¿Hay reglas de negocio mezcladas con detalles técnicos?

### 12. Funciones/métodos largos o con muchos parámetros (Tam) — OK

- **Qué mide:** Tamaño de las funciones/métodos y cantidad de parámetros.
- **Por qué importa:** Una función que hace varias cosas cuesta leerla, nombrarla y reutilizarla.
- **Tu resultado:** **210** función/método(s) largos o con muchos parámetros _(máximo 10 por 1000 LOC)_

### 13. Acoplamiento alto (Acop) — OK

- **Qué mide:** Cuánto depende una unidad de las partes internas de otra.
- **Por qué importa:** Piezas muy enlazadas hacen que un cambio se propague y que sea difícil reemplazar partes.
- **Tu resultado:** **13** unidad(es) con acoplamiento alto _(máximo 2 por 1000 LOC)_

### 14. Cobertura de tests (Cob) — A REVISAR

- **Qué mide:** Porcentaje de líneas de código ejecutadas por la suite de tests (cobertura real, no cantidad de archivos de test).
- **Por qué importa:** Un test que existe pero no ejecuta el código no protege de nada: la cobertura muestra qué partes quedan sin verificar.
- **Tu resultado:** **21.3%** de líneas cubiertas · fuente: ejecución: pytest (. 25.6%, backend 3.0%) _(mínimo 80% de líneas)_
- **Para investigar la causa:**
    - ¿Qué módulos o ramas del sistema nunca se ejecutan en los tests?
    - ¿Los tests prueban el camino principal y los errores, o solo el caso feliz?
    - ¿La suite se puede correr en CI sin base de datos ni servicios externos?

### 15. Vistas del frontend (Vistas) — OK

- **Qué mide:** Cantidad de vistas/componentes de pantalla del frontend.
- **Por qué importa:** El frontend se mide por pantallas: pocas vistas sugiere poca cobertura de la interfaz pedida.
- **Tu resultado:** **96** vista(s)/componente(s) _(mínimo 8)_

## 5. Qué falta para aprobar

Criterios que hoy están en rojo y, para cada uno, una explicación breve de **cómo corregirlo** hasta alcanzar el nivel de aprobación (perfil `exigente`):

| Criterio | Resultado actual | Meta | Cómo corregirlo |
|---|---|---|---|
| Índice de calidad de servicios (indice) | índice **2/100** | mínimo 60 | El índice es un resumen: sube al corregir los criterios en rojo. Empezá por los de más peso (duplicación ≤15%, SEC y SQL en 0, capas ≥2) y volvé a medir; la meta es ≥60. |
| Secretos hardcodeados (SEC) | **7** secreto(s) hardcodeado(s) | máximo 0 | Sacá el valor del código y leelo de una variable de entorno (`.env` no versionado) o del gestor de secretos; si la credencial estuvo publicada, rotala. Meta: 0 casos. |
| Depuración olvidada (DBG) | **55** mensaje(s) de depuración olvidado(s) | máximo 0 | Borrá `console.log`/`print`/`debugger` del código de producción. Si necesitás registro, usá el logger del proyecto con el nivel adecuado. Meta: 0 casos. |
| Baja cohesión (Coh) | **1** unidad(es) con baja cohesión | máximo 0 | Separá la clase en unidades con una sola responsabilidad: si los métodos cambian por motivos distintos, son clases distintas. Meta: 0 clases con baja cohesión. |
| Complejidad alta (Compl) | **279** bloque(s) de complejidad alta | máximo 5 por 1000 LOC (tenés 26232 LOC) | Extraé condiciones y ramas a funciones con nombre propio, usá retornos tempranos y evitá anidar `if`/`switch`. Meta: ≤5 bloques por 1000 LOC. |
| Cobertura de tests (Cob) | **21.3%** de líneas cubiertas · fuente: ejecución: pytest (. 25.6%, backend 3.0%) | mínimo 80% de líneas | Agregá o ampliá tests que ejecuten los módulos sin cubrir (camino principal y errores) y publicá el artefacto (`coverage/lcov.info`, `coverage-summary.json`, `coverage.xml` o `coverage.json`) o corré la suite con coverage. Meta: ≥80% de líneas. |

> Empezá por las señales de seguridad (**SEC**, **SQL**) y por la **duplicación**: son las que más pesan en el índice y las más rápidas de verificar a ojo. Después de corregir, volvé a correr la medición: el semáforo se recalcula sobre `main`.

## 6. Anexo: dónde mirar

Archivos donde el análisis encontró cada señal en rojo (sin número de línea, a propósito):

**Secretos hardcodeados (SEC)** — 3 archivo(s):
- `backend_fastapi/app/services/publish_service.py`
- `frontend_vue/src/views/AuthView.vue`
- `frontend_vue/src/views/SettingsView.vue`

**Depuración olvidada (DBG)** — 8 archivo(s):
- `app/services/hook_service.py`
- `backend/handler.py`
- `backend_express/scripts/audit-openapi.mjs`
- `backend_express/scripts/audit-parity.mjs`
- `backend_express/src/routes/jobs.ts`
- `backend_fastapi/app/main.py`
- `editor_viral.py`
- `scripts/make_og_image.py`

**Baja cohesión (Coh)** — 1 archivo(s):
- `editor_viral.py`

**Complejidad alta (Compl)** — 102 archivo(s):
- `app/services/hook_service.py`
- `audio_analyzer.py`
- `backend/api/routes/retrim.py`
- `backend/api/routes/stream.py`
- `backend/core/security/ssrf_guard.py`
- `backend/core/security/vault.py`
- `backend/handler.py`
- `backend/services/ai_viral/analyzer.py`
- `backend/services/video_editor/renderer.py`
- `backend/track_a/ingestion/service.py`
- `backend/track_b/virality/engine.py`
- `backend_express/src/db/index.ts`
- `backend_express/src/routes/auth.ts`
- `backend_express/src/routes/clips.ts`
- `backend_express/src/routes/export.ts`
- `backend_express/src/routes/jobs.ts`
- `backend_express/src/routes/metrics.ts`
- `backend_express/src/routes/publish.ts`
- `backend_express/src/routes/socialAuth.ts`
- `backend_express/src/routes/subtitles.ts`
- `backend_express/src/routes/users.ts`
- `backend_express/src/routes/videos.ts`
- `backend_express/src/services/runpod.ts`
- `backend_fastapi/app/cli.py`
- `backend_fastapi/app/config.py`
- `backend_fastapi/app/database.py`
- `backend_fastapi/app/main.py`
- `backend_fastapi/app/routers/clips.py`
- `backend_fastapi/app/routers/export.py`
- `backend_fastapi/app/routers/jobs.py`
- `backend_fastapi/app/routers/metrics.py`
- `backend_fastapi/app/routers/publish.py`
- `backend_fastapi/app/routers/sample.py`
- `backend_fastapi/app/routers/social_auth.py`
- `backend_fastapi/app/routers/stats.py`
- `backend_fastapi/app/routers/stream.py`
- `backend_fastapi/app/routers/users.py`
- `backend_fastapi/app/routers/videos.py`
- `backend_fastapi/app/schemas/usuario.py`
- `backend_fastapi/app/services/ass_generator.py`
- `backend_fastapi/app/services/claude_service.py`
- `backend_fastapi/app/services/editor.py`
- `backend_fastapi/app/services/engine.py`
- `backend_fastapi/app/services/ffmpeg_service.py`
- `backend_fastapi/app/services/hook_service.py`
- `backend_fastapi/app/services/instagram_service.py`
- `backend_fastapi/app/services/publish_service.py`
- `backend_fastapi/app/services/runpod_service.py`
- `backend_fastapi/app/services/social_common.py`
- `backend_fastapi/app/services/tiktok_service.py`
- `backend_fastapi/app/services/transcript_utils.py`
- `backend_fastapi/app/services/whisper_service.py`
- `backend_fastapi/app/services/youtube_service.py`
- `backend_fastapi/app/tasks/subtitle_pipeline.py`
- `backend_fastapi/tests/test_e2e_pipeline.py`
- `editor_viral.py`
- `ejemplo_engine.py`
- `engine.py`
- `engine_subprocess.py`
- `frontend_react/src/components/Avatar.tsx`
- `frontend_react/src/components/Navbar.tsx`
- `frontend_react/src/components/auth/AuthForm.tsx`
- `frontend_react/src/components/auth/AuthProvider.tsx`
- `frontend_react/src/components/clip-library/ClipCard.tsx`
- `frontend_react/src/components/clip-library/ClipResults.tsx`
- `frontend_react/src/components/dashboard/DashboardContent.tsx`
- `frontend_react/src/components/dashboard/KpiGrid.tsx`
- `frontend_react/src/components/job-status/CompletedClips.tsx`
- `frontend_react/src/components/job-status/JobProgress.tsx`
- `frontend_react/src/components/landing/LandingHowItWorks.tsx`
- `frontend_react/src/components/upload/DirectUploadPanel.tsx`
- `frontend_react/src/hooks/useIntegrations.ts`
- `frontend_react/src/hooks/useJobPolling.ts`
- `frontend_react/src/hooks/usePublishSSE.ts`
- `frontend_react/src/hooks/useUploadAndProcess.ts`
- `frontend_react/src/lib/apiClient.ts`
- `frontend_react/src/pages/AuthPage.tsx`
- `frontend_react/src/pages/ClipLibraryPage.tsx`
- `frontend_react/src/pages/DashboardPage.tsx`
- `frontend_react/src/pages/IntegrationsPage.tsx`
- `frontend_react/src/pages/JobStatusPage.tsx`
- `frontend_react/src/pages/SettingsPage.tsx`
- `frontend_react/src/pages/UploadPage.tsx`
- `frontend_react/src/services/api.ts`
- `frontend_vue/src/api/services.ts`
- `frontend_vue/src/components/Avatar.vue`
- `frontend_vue/src/components/Navbar.vue`
- `frontend_vue/src/components/landing/LandingHowItWorks.vue`
- `frontend_vue/src/composables/useClipLibrary.ts`
- `frontend_vue/src/composables/useIntegrations.ts`
- `frontend_vue/src/composables/useJobPolling.ts`
- `frontend_vue/src/composables/usePublishStream.ts`
- `frontend_vue/src/stores/auth.ts`
- `frontend_vue/src/views/JobStatusView.vue`
- `frontend_vue/src/views/SettingsView.vue`
- `frontend_vue/src/views/UploadView.vue`
- `limpiar.py`
- `main.py`
- `scripts/make_og_image.py`
- `scripts/test_hooks.py`
- `scripts/test_subtitles.py`
- `whisper_transcriber.py`

---
_Informe generado por la cátedra. Los umbrales corresponden al perfil `exigente`. Ante dudas, revisá el archivo señalado y el criterio en `CRITERIOS-CALIDAD.md`._
<!-- evaluacion:fin -->
