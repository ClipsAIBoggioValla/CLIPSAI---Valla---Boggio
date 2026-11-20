<!-- evaluacion:inicio -->
# Evaluación — ClipsAIBoggioValla/CLIPSAI---Valla---Boggio

> Documento **generado automáticamente** por la cátedra de Programación III (RepoSense + análisis de calidad + constancia). **No editar a mano**: se regenera en cada evaluación.
> Rama evaluada: `main`. Análisis **heurístico** (regex + métricas): es una criba para orientar la revisión, **no una nota**.
> Generado: 2026-11-20.

## 1. Veredicto

| Aspecto | Resultado |
|---|---|
| Tipo de proyecto | app |
| Índice de calidad de servicios | **49/100** (mínimo 50) |
| Criterios cumplidos | **13/16** |
| Aprobado (semáforo) | **NO** |
| Código (LOC) | 31,793 |
| Archivos de código | 247 |
| Tests (archivos) | 24 |
| Cobertura de líneas | 76.9% (mínimo 80%) |
| Capas detectadas | presentacion, logica, datos, vistas, servicios, estado |
| Pushes directos a `main` (sin PR) | 6 |

> **Pushes directos:** se detectaron **6** commit(s) a `main` que no pasaron por un Pull Request. El flujo esperado es **rama → PR → revisión → merge**; el PR se aprueba con el mensaje `Aprobado`. Evitá pushear directo a `main`: la ruleset lo bloquea y el commit directo queda auditado.

> **Aprobado** exige las compuertas críticas (**SEC**, **SQL**, **capas**, **índice ≥ 50** y **cobertura ≥ 80 %** cuando aplica) y tolera hasta **3 criterios en rojo** (12/15). No es una nota: sirve para ordenar y priorizar la revisión.

## 2. Autoría (RepoSense)

| Autor | Commits | Código (LOC) | Tests (LOC) | Docs (LOC) | Días activos | % del código |
|---|---:|---:|---:|---:|---:|---:|
| mateo | 133 | 30,831 | 9,186 | 2,155 | 49 | 78% |
| SantiValla | 39 | 8,888 | 45 | 591 | 13 | 22% |

> _El LOC de autoría lo calcula RepoSense sobre el historial y puede diferir del LOC de código del análisis de calidad (que mira solo el estado de `main`)._

> **Reparto del trabajo:** mateo concentra el 78% de las líneas de código. Un reparto muy desigual suele indicar que la integración no fue realmente en equipo; vale la pena reconstruir cómo se coordinó.

## 3. Constancia (IC) — todas las ramas

> El IC mide **cuándo** se trabajó (sesiones por semana, pausas y recencia), no cuánto ni con qué calidad. Se calcula sobre **todas las ramas** de todos los repositorios del alumno, no sólo `main`.

| Alumno | Sesiones | Cumplimiento | Pausa | Recencia | IC | Nivel | Para subir de nivel |
|---|--:|--:|--:|--:|--:|--|--|
| mateo | 40 | 100% | 12 d | 93% | **78** | Aprueba | Pausa 12 d (máx. 5 d) |
| SantiValla | 17 | 60% | 19 d | 36% | **44** | No aprueba | Recencia 36% (mín. 50%) |

> Para aprobar el IC: **2 sesiones por semana** sostenidas, sin pausas mayores a **10 días** y con actividad en las **últimas 2 semanas**. Se excluyen merges, bots y al docente. Zona horaria UTC-3.

## 4. Aspectos evaluados

Cada aspecto indica **qué mide**, **por qué importa** y **tu resultado**. Cuando el resultado está en rojo, se agregan preguntas para **investigar la causa** (no hay recetas: entender el porqué es parte de la evaluación).

### 1. Índice de calidad de servicios (indice) — A REVISAR

- **Qué mide:** Un resumen numérico (0-100) que combina todas las señales y métricas del análisis, con topes duros por duplicación.
- **Por qué importa:** Ordena y prioriza la revisión: un índice bajo indica varias señales que conviene mirar juntas.
- **Tu resultado:** índice **49/100** _(mínimo 50)_
- **Para investigar la causa:**
    - ¿En qué momento del proyecto se concentraron los problemas (arranque, integración de partes, cierre)?
    - ¿El índice bajó por muchas señales chicas o por una o dos graves?
    - ¿Se revisó el código integrado después de unir el trabajo de cada integrante?

### 2. Duplicación (DRY) (duplicacion) — OK

- **Qué mide:** Porcentaje de bloques de código repetidos (similitud) en el repositorio.
- **Por qué importa:** Cada copia se mantiene por separado: un arreglo hay que repetirlo y los defectos se multiplican.
- **Tu resultado:** **7.2%** de duplicación _(máximo 15%)_

### 3. Secretos hardcodeados (SEC) — OK

- **Qué mide:** Credenciales, tokens o claves escritos directamente en el código en vez de leerse de variables de entorno.
- **Por qué importa:** Un secreto en el repositorio queda expuesto en el historial aunque luego se borre, y compromete al servicio y a sus usuarios.
- **Tu resultado:** **0** secreto(s) hardcodeado(s) _(máximo 0)_

### 4. Consultas SQL por concatenación (SQL) — OK

- **Qué mide:** Consultas SQL armadas concatenando o interpolando valores en vez de usar parámetros.
- **Por qué importa:** Es la puerta clásica a inyección: un valor que llega de afuera puede cambiar la consulta.
- **Tu resultado:** **0** consulta(s) SQL por concatenación _(máximo 0)_

### 5. Separación en capas (capas) — OK

- **Qué mide:** Si el código está separado en capas reconocibles (backend: presentación / lógica / datos; frontend: vistas / servicios / estado).
- **Por qué importa:** Sin separación, cada archivo hace de todo y cualquier cambio toca varios lugares a la vez.
- **Tu resultado:** **6** capa(s) detectada(s): presentacion, logica, datos, vistas, servicios, estado _(mínimo 2 capas (a partir de 150 LOC))_

### 6. Acceso a datos dentro del componente (HTTP) — OK

- **Qué mide:** Llamadas `fetch`/`axios` dentro de componentes de UI en vez de una capa de servicios/API.
- **Por qué importa:** Duplica la lógica de acceso a datos y acopla la vista al backend: un cambio de API toca muchos componentes.
- **Tu resultado:** **0** llamada(s) a la API dentro de componente(s) _(máximo 0)_

### 7. Depuración olvidada (DBG) — OK

- **Qué mide:** Mensajes de depuración olvidados (`console.log`, `print`, `debugger`).
- **Por qué importa:** Generan ruido en los registros, pueden filtrar datos y dan sensación de código sin terminar.
- **Tu resultado:** **0** mensaje(s) de depuración olvidado(s) _(máximo 0)_

### 8. Uso del tipo `any` (Any) — OK

- **Qué mide:** Uso de `any` en TypeScript, que desactiva la verificación de tipos.
- **Por qué importa:** Se pierde la ayuda del compilador justo donde los datos vienen de afuera (API, formularios).
- **Tu resultado:** **0** uso(s) de `any` _(máximo 2)_

### 9. Componente demasiado grande (BigC) — A REVISAR

- **Qué mide:** Componentes de UI muy extensos, que suelen mezclar render, estado y lógica.
- **Por qué importa:** Son difíciles de leer, probar y reutilizar, y sus cambios tienen efectos inesperados.
- **Tu resultado:** **8** componente(s) demasiado grande(s) _(máximo 1)_
- **Para investigar la causa:**
    - ¿El componente creció a medida que se agregaban requisitos, sin volver a dividirlo?
    - ¿Mezcla responsabilidades distintas (mostrar, calcular, pedir datos)?
    - ¿Se dividió por pantalla o por unidad de responsabilidad?

### 10. Baja cohesión (Coh) — OK

- **Qué mide:** Una clase o unidad cuyos métodos y campos no están relacionados entre sí.
- **Por qué importa:** Una unidad que cambia por motivos distintos es frágil y cuesta entenderla.
- **Tu resultado:** **0** unidad(es) con baja cohesión _(máximo 0)_

### 11. Complejidad alta (Compl) — OK

- **Qué mide:** Complejidad ciclomática: cantidad de caminos posibles dentro de una función (condicionales, bucles, casos).
- **Por qué importa:** Muchos caminos = difícil de seguir y de probar; suelen esconderse casos sin cubrir.
- **Tu resultado:** **67** bloque(s) de complejidad alta _(máximo 5 por 1000 LOC (tenés 31793 LOC))_

### 12. Funciones/métodos largos o con muchos parámetros (Tam) — OK

- **Qué mide:** Tamaño de las funciones/métodos y cantidad de parámetros.
- **Por qué importa:** Una función que hace varias cosas cuesta leerla, nombrarla y reutilizarla.
- **Tu resultado:** **207** función/método(s) largos o con muchos parámetros _(máximo 10 por 1000 LOC)_

### 13. Acoplamiento alto (Acop) — OK

- **Qué mide:** Cuánto depende una unidad de las partes internas de otra.
- **Por qué importa:** Piezas muy enlazadas hacen que un cambio se propague y que sea difícil reemplazar partes.
- **Tu resultado:** **11** unidad(es) con acoplamiento alto _(máximo 2 por 1000 LOC)_

### 14. Cobertura de tests (Cob) — A REVISAR

- **Qué mide:** Porcentaje de líneas de código ejecutadas por la suite de tests (cobertura real, no cantidad de archivos de test).
- **Por qué importa:** Un test que existe pero no ejecuta el código no protege de nada: la cobertura muestra qué partes quedan sin verificar.
- **Tu resultado:** **76.9%** de líneas cubiertas · fuente: ejecución: pytest (aviso: requirements.txt: sin instalar 2 línea(s) (no disponibles o en conflicto: torch>=2.1.0 --index-url https://dow…) (. 75.5%, backend_fastapi 79.0%) _(mínimo 80% de líneas)_
- **Para investigar la causa:**
    - ¿Qué módulos o ramas del sistema nunca se ejecutan en los tests?
    - ¿Los tests prueban el camino principal y los errores, o solo el caso feliz?
    - ¿La suite se puede correr en CI sin base de datos ni servicios externos?

### 15. Endpoints del backend (EP) — OK

- **Qué mide:** Cantidad de endpoints (rutas HTTP) expuestos por el backend.
- **Por qué importa:** El backend se mide por lo que expone: pocos endpoints sugiere poca funcionalidad de servicio.
- **Tu resultado:** **117** endpoint(s) _(mínimo 5)_

### 16. Vistas del frontend (Vistas) — OK

- **Qué mide:** Cantidad de vistas/componentes de pantalla del frontend.
- **Por qué importa:** El frontend se mide por pantallas: pocas vistas sugiere poca cobertura de la interfaz pedida.
- **Tu resultado:** **96** vista(s)/componente(s) _(mínimo 6)_

## 5. Observaciones y qué falta

Criterios que hoy están en rojo y, para cada uno, una explicación breve de **cómo corregirlo** hasta alcanzar el nivel de aprobación (perfil `exigente`):

| Criterio | Resultado actual | Meta | Brecha | Cómo alcanzarlo |
|---|---|---|---|---|
| Índice de calidad de servicios (indice) | índice **49/100** | mínimo 50 | faltan 1 pts | El índice sólo penaliza lo que **excede** los umbrales de cada criterio: si tenés todo en verde, el índice es 100. Si está en rojo, mirá la columna **Brecha** y los criterios en rojo; corregí primero duplicación, SEC, SQL y capas. Meta del perfil exigente: ≥50. |
| Componente demasiado grande (BigC) | **8** componente(s) demasiado grande(s) | máximo 1 | 7 componente(s) de más | Dividí el componente por responsabilidad en subcomponentes (render, estado, acceso a datos) y dejá el original sólo como orquestador. Meta: ≤1 componente grande. |
| Cobertura de tests (Cob) | **76.9%** de líneas cubiertas · fuente: ejecución: pytest (aviso: requirements.txt: sin instalar 2 línea(s) (no disponibles o en conflicto: torch>=2.1.0 --index-url https://dow…) (. 75.5%, backend_fastapi 79.0%) | mínimo 80% de líneas | faltan 3.1 pts | Agregá o ampliá tests que ejecuten los módulos sin cubrir (camino principal y errores) y publicá el artefacto (`coverage/lcov.info`, `coverage-summary.json`, `coverage.xml` o `coverage.json`) o corré la suite con coverage. Meta: ≥80% de líneas. |

> Empezá por las señales de seguridad (**SEC**, **SQL**) y por la **duplicación**: son las que más pesan en el índice y las más rápidas de verificar a ojo. Después de corregir, volvé a correr la medición: el semáforo se recalcula sobre `main`.

## 6. Actividad en clase y fuera de clase

> Se consideran las **29 clases** del período (miércoles y viernes, según `config/constancia.json`; feriados y semanas sin clase descontados). Para cada alumno se muestra la actividad **en cada clase** y también la actividad **fuera de los días de clase** (fines de semana u otros días). `Commits` = commits de trabajo (no-merge); `Merges` = merges de PR (también son push). Los días sin actividad dicen **sin actividad**.

### mateo

**19/29 clases con actividad** · total del período: 81 commits · 27 merges

| Fecha | Actividad | Repositorios | Commits / merges |
|---|:--:|---|--:|
| 2026-08-14 | No | sin actividad | 0 / 0 |
| 2026-08-19 | **Sí** | CLIPSAI---Valla---Boggio | 7 / 0 |
| 2026-08-21 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-08-26 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-08-28 | No | sin actividad | 0 / 0 |
| 2026-09-02 | **Sí** | CLIPSAI---Valla---Boggio | 7 / 4 |
| 2026-09-04 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 3 |
| 2026-09-09 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-09-11 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 1 |
| 2026-09-16 | No | sin actividad | 0 / 0 |
| 2026-09-18 | No | sin actividad | 0 / 0 |
| 2026-09-23 | No | sin actividad | 0 / 0 |
| 2026-09-25 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-09-30 | No | sin actividad | 0 / 0 |
| 2026-10-02 | **Sí** | CLIPSAI---Valla---Boggio | 8 / 5 |
| 2026-10-07 | **Sí** | CLIPSAI---Valla---Boggio | 4 / 3 |
| 2026-10-09 | **Sí** | CLIPSAI---Valla---Boggio | 5 / 0 |
| 2026-10-14 | No | sin actividad | 0 / 0 |
| 2026-10-16 | No | sin actividad | 0 / 0 |
| 2026-10-21 | **Sí** | CLIPSAI---Valla---Boggio | 5 / 3 |
| 2026-10-23 | **Sí** | CLIPSAI---Valla---Boggio | 8 / 0 |
| 2026-10-28 | **Sí** | CLIPSAI---Valla---Boggio | 9 / 0 |
| 2026-10-30 | **Sí** | CLIPSAI---Valla---Boggio | 10 / 0 |
| 2026-11-04 | **Sí** | CLIPSAI---Valla---Boggio | 3 / 0 |
| 2026-11-06 | **Sí** | CLIPSAI---Valla---Boggio | 0 / 2 |
| 2026-11-11 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 2 |
| 2026-11-13 | No | sin actividad | 0 / 0 |
| 2026-11-18 | **Sí** | CLIPSAI---Valla---Boggio | 4 / 2 |
| 2026-11-20 | No | sin actividad | 0 / 0 |

**Fuera de clase:** 30 fecha(s) con actividad · 61 commits · 26 merges

| Fecha | Repositorios | Commits / merges |
|---|---|--:|
| 2026-08-24 | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-08-25 | CLIPSAI---Valla---Boggio | 2 / 1 |
| 2026-08-31 | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-09-01 | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-09-03 | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-09-05 | CLIPSAI---Valla---Boggio | 3 / 1 |
| 2026-09-07 | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-09-08 | CLIPSAI---Valla---Boggio | 1 / 2 |
| 2026-09-10 | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-09-12 | CLIPSAI---Valla---Boggio | 2 / 3 |
| 2026-09-19 | CLIPSAI---Valla---Boggio | 2 / 1 |
| 2026-09-20 | CLIPSAI---Valla---Boggio | 2 / 2 |
| 2026-09-21 | CLIPSAI---Valla---Boggio | 0 / 1 |
| 2026-10-03 | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-10-04 | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-10-06 | CLIPSAI---Valla---Boggio | 1 / 2 |
| 2026-10-08 | CLIPSAI---Valla---Boggio | 0 / 1 |
| 2026-10-10 | CLIPSAI---Valla---Boggio | 0 / 1 |
| 2026-10-18 | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-10-19 | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-10-20 | CLIPSAI---Valla---Boggio | 0 / 1 |
| 2026-10-24 | CLIPSAI---Valla---Boggio | 7 / 0 |
| 2026-10-26 | CLIPSAI---Valla---Boggio | 5 / 0 |
| 2026-10-27 | CLIPSAI---Valla---Boggio | 3 / 0 |
| 2026-11-05 | CLIPSAI---Valla---Boggio | 8 / 0 |
| 2026-11-08 | CLIPSAI---Valla---Boggio | 2 / 1 |
| 2026-11-09 | CLIPSAI---Valla---Boggio | 2 / 2 |
| 2026-11-10 | CLIPSAI---Valla---Boggio | 4 / 1 |
| 2026-11-12 | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-11-19 | CLIPSAI---Valla---Boggio | 2 / 0 |

### SantiValla

**18/29 clases con actividad** · total del período: 45 commits · 10 merges

| Fecha | Actividad | Repositorios | Commits / merges |
|---|:--:|---|--:|
| 2026-08-14 | No | sin actividad | 0 / 0 |
| 2026-08-19 | No | sin actividad | 0 / 0 |
| 2026-08-21 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-08-26 | No | sin actividad | 0 / 0 |
| 2026-08-28 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-09-02 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-09-04 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-09-09 | No | sin actividad | 0 / 0 |
| 2026-09-11 | No | sin actividad | 0 / 0 |
| 2026-09-16 | No | sin actividad | 0 / 0 |
| 2026-09-18 | No | sin actividad | 0 / 0 |
| 2026-09-23 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-09-25 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 1 |
| 2026-09-30 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 3 |
| 2026-10-02 | **Sí** | CLIPSAI---Valla---Boggio | 3 / 1 |
| 2026-10-07 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 1 |
| 2026-10-09 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-10-14 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-10-16 | **Sí** | CLIPSAI---Valla---Boggio | 10 / 1 |
| 2026-10-21 | **Sí** | CLIPSAI---Valla---Boggio | 14 / 0 |
| 2026-10-23 | **Sí** | CLIPSAI---Valla---Boggio | 2 / 0 |
| 2026-10-28 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-10-30 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 2 |
| 2026-11-04 | No | sin actividad | 0 / 0 |
| 2026-11-06 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-11-11 | **Sí** | CLIPSAI---Valla---Boggio | 1 / 0 |
| 2026-11-13 | No | sin actividad | 0 / 0 |
| 2026-11-18 | No | sin actividad | 0 / 0 |
| 2026-11-20 | No | sin actividad | 0 / 0 |

**Fuera de clase:** sin actividad registrada.

## 7. Anexo: archivos donde se originan los problemas

Se listan **todos** los archivos y líneas que el análisis marca para cada criterio en rojo. Para **duplicación** se muestran los archivos con líneas repetidas; para **cobertura**, las unidades por debajo del umbral.

**Resumen por archivo** — archivos con más hallazgos:

| Archivo | Hallazgos | Peso total | Señales |
|---|---:|---:|---|
| `backend_fastapi/app/routers/jobs.py` | 26 | 104 | long_function, long_params |
| `backend_fastapi/app/services/publish_service.py` | 13 | 52 | long_function, long_params |
| `frontend_react/src/pages/ClipLibraryPage.tsx` | 9 | 44 | high_complexity, long_function |
| `frontend_react/src/hooks/usePublishSSE.ts` | 8 | 36 | high_complexity, long_function |
| `backend_fastapi/app/routers/clips.py` | 7 | 28 | long_function, long_params |
| `backend_fastapi/app/services/ass_generator.py` | 7 | 28 | long_params |
| `main.py` | 7 | 29 | high_complexity, long_function, long_params |
| `video_processor.py` | 7 | 28 | long_function, long_params |
| `backend/handler.py` | 6 | 25 | high_complexity, long_function, long_params |
| `backend_express/src/routes/clips.ts` | 6 | 25 | high_complexity, long_function, long_params |
| `backend_fastapi/app/services/engine.py` | 6 | 24 | long_function, long_params |
| `backend_fastapi/app/services/ffmpeg_service.py` | 6 | 24 | long_function, long_params |
| `backend_fastapi/app/services/claude_service.py` | 5 | 20 | long_function, long_params |
| `frontend_react/src/pages/DashboardPage.tsx` | 5 | 23 | big_component, high_complexity, long_function, long_params |
| `backend_fastapi/app/routers/social_auth.py` | 4 | 16 | long_params |
| `frontend_react/src/pages/JobStatusPage.tsx` | 4 | 20 | big_component, high_complexity, long_function |
| `frontend_react/src/pages/SettingsPage.tsx` | 4 | 20 | big_component, high_complexity, long_function |
| `frontend_vue/src/composables/useJobPolling.ts` | 4 | 18 | high_complexity, long_function |
| `whisper_transcriber.py` | 4 | 16 | long_function, long_params |
| `app/services/hook_service.py` | 3 | 12 | long_function, long_params |
| `audio_analyzer.py` | 3 | 12 | long_function, long_params |
| `backend_express/src/routes/publish.ts` | 3 | 14 | high_complexity, long_params |
| `backend_express/src/services/runpod.ts` | 3 | 12 | long_params |
| `backend_fastapi/app/services/hook_service.py` | 3 | 12 | long_function, long_params |
| `backend_fastapi/app/services/runpod_service.py` | 3 | 12 | long_function, long_params |
| … | … | … | y 89 archivo(s) más |

**Índice (indice)** — todos los hallazgos que lo afectan:

| Archivo:línea | Señal | Peso | Detalle |
|---|---|---:|---|
| `backend/core/schemas.py:115` | high_coupling | 8 | clase 'ScheduledPost' muy acoplada (CBO=8) |
| `backend/track_a/ingestion/service.py:15` | high_coupling | 8 | clase 'IngestionService' muy acoplada (CBO=9) |
| `backend/track_b/publishing/scheduler.py:7` | high_coupling | 8 | clase 'MockPublisher' muy acoplada (CBO=8) |
| `backend/track_b/rendering/ffmpeg.py:7` | high_coupling | 8 | clase 'FFmpegRenderer' muy acoplada (CBO=13) |
| `backend_fastapi/app/config.py:79` | high_coupling | 8 | clase 'Settings' muy acoplada (CBO=62) |
| `backend_fastapi/app/models/clip.py:17` | high_coupling | 8 | clase 'Clip' muy acoplada (CBO=16) |
| `backend_fastapi/app/models/job.py:25` | high_coupling | 8 | clase 'Job' muy acoplada (CBO=11) |
| `backend_fastapi/app/models/social_account.py:16` | high_coupling | 8 | clase 'SocialAccount' muy acoplada (CBO=12) |
| `backend_fastapi/app/models/video.py:16` | high_coupling | 8 | clase 'Video' muy acoplada (CBO=9) |
| `editor_viral.py:112` | high_coupling | 8 | clase 'RenderizadorVertical' muy acoplada (CBO=11) |
| `editor_viral.py:193` | high_coupling | 8 | clase 'VideoEditor' muy acoplada (CBO=21) |
| `frontend_react/src/components/clip-library/ClipResults.tsx:1` | big_component | 6 | componente grande (180 líneas) |
| `frontend_react/src/pages/DashboardPage.tsx:1` | big_component | 6 | componente grande (428 líneas) |
| `frontend_react/src/pages/IntegrationsPage.tsx:1` | big_component | 6 | componente grande (164 líneas) |
| `frontend_react/src/pages/JobStatusPage.tsx:1` | big_component | 6 | componente grande (182 líneas) |
| `frontend_react/src/pages/SettingsPage.tsx:1` | big_component | 6 | componente grande (168 líneas) |
| `frontend_react/src/pages/UploadPage.tsx:1` | big_component | 6 | componente grande (173 líneas) |
| `frontend_vue/src/views/JobStatusView.vue:1` | big_component | 6 | componente grande (156 líneas) |
| `frontend_vue/src/views/SettingsView.vue:1` | big_component | 6 | componente grande (171 líneas) |
| `backend/api/routes/stream.py:47` | high_complexity | 5 | función '_progress_gen' con complejidad 9 |
| `backend/core/security/vault.py:15` | high_complexity | 5 | función '_get_key' con complejidad 6 |
| `backend/handler.py:344` | high_complexity | 5 | función 'process_video_job' con complejidad 6 |
| `backend_express/src/routes/auth.ts:67` | high_complexity | 5 | función 'handleRegistro' con complejidad 11 |
| `backend_express/src/routes/auth.ts:114` | high_complexity | 5 | función 'handleLogin' con complejidad 7 |
| `backend_express/src/routes/clips.ts:455` | high_complexity | 5 | función 'removeClipFile' con complejidad 8 |
| `backend_express/src/routes/publish.ts:133` | high_complexity | 5 | función 'handlePublish' con complejidad 8 |
| `backend_express/src/routes/publish.ts:241` | high_complexity | 5 | función 'publishStreamTick' con complejidad 6 |
| `backend_express/src/routes/socialAuth.ts:644` | high_complexity | 5 | función 'tiktokCallbackOutcome' con complejidad 7 |
| `backend_express/src/routes/users.ts:310` | high_complexity | 5 | función 'handleChangePassword' con complejidad 7 |
| `backend_express/src/routes/videos.ts:93` | high_complexity | 5 | función 'async' con complejidad 10 |
| `backend_express/src/routes/videos.ts:225` | high_complexity | 5 | función 'async' con complejidad 6 |
| `backend_fastapi/app/routers/videos.py:166` | high_complexity | 5 | función '_save_upload_file' con complejidad 6 |
| `backend_fastapi/app/services/transcript_utils.py:16` | high_complexity | 5 | función 'parse_transcript_text_to_segments' con complejidad 14 |
| `ejemplo_engine.py:25` | high_complexity | 5 | función 'main' con complejidad 13 |
| `frontend_react/src/components/Navbar.tsx:62` | high_complexity | 5 | función 'handleSearch' con complejidad 8 |
| `frontend_react/src/components/Navbar.tsx:66` | high_complexity | 5 | función 'toggleFullscreen' con complejidad 8 |
| `frontend_react/src/components/auth/AuthForm.tsx:21` | high_complexity | 5 | función 'AuthForm' con complejidad 18 |
| `frontend_react/src/components/auth/AuthProvider.tsx:31` | high_complexity | 5 | función 'useEffect' con complejidad 9 |
| `frontend_react/src/components/clip-library/ClipCard.tsx:17` | high_complexity | 5 | función 'ClipCard' con complejidad 6 |
| `frontend_react/src/components/clip-library/ClipResults.tsx:73` | high_complexity | 5 | función 'ClipResults' con complejidad 13 |
| `frontend_react/src/components/dashboard/DashboardContent.tsx:9` | high_complexity | 5 | función 'DashboardContent' con complejidad 17 |
| `frontend_react/src/components/dashboard/KpiGrid.tsx:8` | high_complexity | 5 | función 'KpiGrid' con complejidad 10 |
| `frontend_react/src/components/job-status/CompletedClips.tsx:11` | high_complexity | 5 | función 'CompletedClips' con complejidad 21 |
| `frontend_react/src/components/job-status/JobProgress.tsx:7` | high_complexity | 5 | función 'JobProgress' con complejidad 14 |
| `frontend_react/src/components/landing/LandingHowItWorks.tsx:5` | high_complexity | 5 | función 'LandingHowItWorks' con complejidad 10 |
| `frontend_react/src/components/upload/DirectUploadPanel.tsx:11` | high_complexity | 5 | función 'DirectUploadPanel' con complejidad 23 |
| `frontend_react/src/hooks/useIntegrations.ts:46` | high_complexity | 5 | función 'connectSocial' con complejidad 6 |
| `frontend_react/src/hooks/useIntegrations.ts:59` | high_complexity | 5 | función 'useIntegrations' con complejidad 8 |
| `frontend_react/src/hooks/useJobPolling.ts:120` | high_complexity | 5 | función 'useJobPolling' con complejidad 9 |
| `frontend_react/src/hooks/usePublishSSE.ts:67` | high_complexity | 5 | función 'applySseStatus' con complejidad 10 |
| `frontend_react/src/hooks/usePublishSSE.ts:68` | high_complexity | 5 | función 'applySseFields' con complejidad 10 |
| `frontend_react/src/hooks/usePublishSSE.ts:71` | high_complexity | 5 | función 'usePublishSSE' con complejidad 10 |
| `frontend_react/src/hooks/usePublishSSE.ts:78` | high_complexity | 5 | función 'useEffect' con complejidad 10 |
| `frontend_react/src/lib/apiClient.ts:94` | high_complexity | 5 | función 'redirectToLoginIfOutside' con complejidad 6 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:24` | high_complexity | 5 | función 'ClipLibraryPage' con complejidad 36 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:69` | high_complexity | 5 | función 'useEffect' con complejidad 11 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:99` | high_complexity | 5 | función 'setCaption' con complejidad 9 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:100` | high_complexity | 5 | función 'setWebhookUrl' con complejidad 8 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:103` | high_complexity | 5 | función 'submitPublish' con complejidad 8 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:125` | high_complexity | 5 | función 'setToast' con complejidad 6 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:126` | high_complexity | 5 | función 'setTimeout' con complejidad 6 |
| `frontend_react/src/pages/ClipLibraryPage.tsx:127` | high_complexity | 5 | función 'setTimeout' con complejidad 6 |
| `frontend_react/src/pages/DashboardPage.tsx:351` | high_complexity | 5 | función 'DashboardPage' con complejidad 11 |
| `frontend_react/src/pages/IntegrationsPage.tsx:88` | high_complexity | 5 | función 'IntegrationsPage' con complejidad 6 |
| `frontend_react/src/pages/JobStatusPage.tsx:119` | high_complexity | 5 | función 'JobStatusPage' con complejidad 16 |
| `frontend_react/src/pages/JobStatusPage.tsx:154` | high_complexity | 5 | función 'useEffect' con complejidad 7 |
| `frontend_react/src/pages/SettingsPage.tsx:88` | high_complexity | 5 | función 'SettingsPage' con complejidad 12 |
| `frontend_react/src/pages/SettingsPage.tsx:110` | high_complexity | 5 | función 'useEffect' con complejidad 6 |
| `frontend_react/src/pages/UploadPage.tsx:77` | high_complexity | 5 | función 'UploadPage' con complejidad 12 |
| `frontend_react/src/services/api.ts:163` | high_complexity | 5 | función 'triggerBlobDownload' con complejidad 7 |
| `frontend_vue/src/api/services.ts:137` | high_complexity | 5 | función 'triggerBlobDownload' con complejidad 10 |
| `frontend_vue/src/components/Avatar.vue:6` | high_complexity | 5 | función 'getInitials' con complejidad 8 |
| `frontend_vue/src/components/Navbar.vue:45` | high_complexity | 5 | función 'watch' con complejidad 7 |
| `frontend_vue/src/components/Navbar.vue:64` | high_complexity | 5 | función 'toggleFullscreen' con complejidad 8 |
| `frontend_vue/src/components/landing/LandingHowItWorks.vue:14` | high_complexity | 5 | función 'onKeydown' con complejidad 9 |
| `frontend_vue/src/composables/useClipLibrary.ts:8` | high_complexity | 5 | función 'useClipLibrary' con complejidad 42 |
| `frontend_vue/src/composables/useIntegrations.ts:38` | high_complexity | 5 | función 'useIntegrations' con complejidad 17 |
| `frontend_vue/src/composables/useJobPolling.ts:59` | high_complexity | 5 | función 'handleUnrecoverablePollFailure' con complejidad 8 |
| `frontend_vue/src/composables/useJobPolling.ts:94` | high_complexity | 5 | función 'useJobPolling' con complejidad 9 |
| `frontend_vue/src/composables/usePublishStream.ts:63` | high_complexity | 5 | función 'usePublishStream' con complejidad 7 |
| `frontend_vue/src/stores/auth.ts:45` | high_complexity | 5 | función 'init' con complejidad 6 |
| `frontend_vue/src/views/JobStatusView.vue:55` | high_complexity | 5 | función 'onMounted' con complejidad 6 |
| `frontend_vue/src/views/JobStatusView.vue:91` | high_complexity | 5 | función 'watch' con complejidad 7 |
| `frontend_vue/src/views/UploadView.vue:63` | high_complexity | 5 | función 'handleSampleJob' con complejidad 6 |
| `frontend_vue/src/views/UploadView.vue:79` | high_complexity | 5 | función 'handleSubmit' con complejidad 8 |
| `main.py:118` | high_complexity | 5 | función '_agregar_momentos_cluster' con complejidad 6 |
| `app/services/hook_service.py:107` | long_function | 4 | función '_build_hook_prompt' de 58 líneas |
| `app/services/hook_service.py:186` | long_params | 4 | función '_post_with_retry' con 5 parámetros |
| `app/services/hook_service.py:303` | long_params | 4 | función '_clip_llm_valido' con 6 parámetros |
| `audio_analyzer.py:61` | long_params | 4 | función '_agregar_evento_nivel' con 5 parámetros |
| `audio_analyzer.py:81` | long_params | 4 | función '_agregar_cambio_brusco' con 6 parámetros |
| `audio_analyzer.py:330` | long_function | 4 | función 'analizar_audio' de 50 líneas |
| `backend/api/routes/retrim.py:107` | long_function | 4 | función '_ffmpeg_retrim' de 35 líneas |
| `backend/api/routes/retrim.py:168` | long_params | 4 | función '_ejecutar_retrim' con 5 parámetros |
| `backend/api/routes/stream.py:47` | long_function | 4 | función '_progress_gen' de 35 líneas |
| `backend/core/interfaces.py:49` | long_params | 4 | método 'IRenderer.render' con 6 parámetros |
| `backend/handler.py:274` | long_params | 4 | función '_clip_vertical_dict' con 5 parámetros |
| `backend/handler.py:291` | long_function | 4 | función '_procesar_clip_vertical' de 37 líneas |
| `backend/handler.py:291` | long_params | 4 | función '_procesar_clip_vertical' con 6 parámetros |
| `backend/handler.py:330` | long_params | 4 | función '_procesar_clips_verticales' con 5 parámetros |
| `backend/handler.py:344` | long_function | 4 | función 'process_video_job' de 88 líneas |
| `backend/services/ai_viral/analyzer.py:15` | long_function | 4 | función '_mock_candidates_from_transcript' de 34 líneas |
| `backend/services/video_editor/renderer.py:122` | long_function | 4 | función 'render_clip' de 51 líneas |
| `backend/services/video_editor/renderer.py:122` | long_params | 4 | función 'render_clip' con 5 parámetros |
| `backend/track_b/rendering/ffmpeg.py:10` | long_params | 4 | método 'FFmpegRenderer.render' con 6 parámetros |
| `backend_express/src/app.ts:18` | long_function | 4 | función 'createApp' de 100 líneas |
| `backend_express/src/docs/swagger.ts:723` | long_function | 4 | función 'buildUserMePaths' de 109 líneas |
| `backend_express/src/routes/clips.ts:455` | long_function | 4 | función 'removeClipFile' de 44 líneas |
| `backend_express/src/routes/clips.ts:586` | long_params | 4 | función 'concatHookInto' con 6 parámetros |
| `backend_express/src/routes/clips.ts:609` | long_params | 4 | función 'buildHookConcat' con 6 parámetros |
| `backend_express/src/routes/clips.ts:731` | long_params | 4 | función 'persistReRenderResult' con 5 parámetros |
| `backend_express/src/routes/clips.ts:771` | long_params | 4 | función 'runReRenderPipeline' con 5 parámetros |
| `backend_express/src/routes/metrics.ts:147` | long_params | 4 | función 'recentActivityEntry' con 8 parámetros |
| `backend_express/src/routes/metrics.ts:159` | long_params | 4 | función 'buildRecentActivity' con 7 parámetros |
| `backend_express/src/routes/publish.ts:66` | long_params | 4 | función 'webhookPublication' con 5 parámetros |
| `backend_express/src/routes/subtitles.ts:77` | long_params | 4 | función 'pushWrappedWord' con 5 parámetros |
| `backend_express/src/routes/users.ts:186` | long_params | 4 | función 'applyBasicFields' con 5 parámetros |
| `backend_express/src/services/runpod.ts:139` | long_params | 4 | función 'callRunpodEndpoint' con 6 parámetros |
| `backend_express/src/services/runpod.ts:163` | long_params | 4 | función 'pollRunpodStatus' con 5 parámetros |
| `backend_express/src/services/runpod.ts:177` | long_params | 4 | función 'pollRunpodJob' con 5 parámetros |
| `backend_express/src/services/s3.ts:88` | long_function | 4 | función 'generatePresignedUrl' de 34 líneas |
| `backend_fastapi/app/cli.py:73` | long_params | 4 | función '_renderizar_clip_cli' con 7 parámetros |
| `backend_fastapi/app/main.py:165` | long_function | 4 | función '_preparar_restricciones' de 36 líneas |
| `backend_fastapi/app/routers/clips.py:245` | long_params | 4 | función '_ajustar_al_segmento_cercano' con 5 parámetros |
| `backend_fastapi/app/routers/clips.py:257` | long_params | 4 | función '_recortar_al_clip' con 5 parámetros |
| `backend_fastapi/app/routers/clips.py:350` | long_params | 4 | función '_re_render_exitoso' con 9 parámetros |
| `backend_fastapi/app/routers/clips.py:425` | long_params | 4 | función '_renderizar_re_render' con 5 parámetros |
| `backend_fastapi/app/routers/clips.py:583` | long_function | 4 | función 'list_clips' de 37 líneas |
| `backend_fastapi/app/routers/clips.py:583` | long_params | 4 | función 'list_clips' con 10 parámetros |
| `backend_fastapi/app/routers/clips.py:670` | long_params | 4 | función 're_render_clip' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:392` | long_params | 4 | función '_validar_args_render' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:498` | long_params | 4 | función '_ass_teaser' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:509` | long_params | 4 | función '_ass_simple' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:518` | long_params | 4 | función '_generar_ass' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:561` | long_params | 4 | función '_cortar_clip_intermedio' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:594` | long_params | 4 | función '_reframar_y_quemar' con 7 parámetros |
| `backend_fastapi/app/routers/jobs.py:632` | long_function | 4 | función '_render_clip_with_ass_and_hook' de 42 líneas |
| `backend_fastapi/app/routers/jobs.py:632` | long_params | 4 | función '_render_clip_with_ass_and_hook' con 8 parámetros |
| `backend_fastapi/app/routers/jobs.py:955` | long_params | 4 | función '_invocar_engine' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1101` | long_params | 4 | función '_cerrar_job_r2' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1130` | long_params | 4 | función '_persistir_clips_r2' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1175` | long_function | 4 | función '_resolver_segmentos' de 30 líneas |
| `backend_fastapi/app/routers/jobs.py:1175` | long_params | 4 | función '_resolver_segmentos' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1328` | long_params | 4 | función '_enriquecer_tags' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1369` | long_params | 4 | función '_registrar_fallo_render' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1392` | long_function | 4 | función '_renderar_clip_item' de 43 líneas |
| `backend_fastapi/app/routers/jobs.py:1392` | long_params | 4 | función '_renderar_clip_item' con 12 parámetros |
| `backend_fastapi/app/routers/jobs.py:1437` | long_params | 4 | función '_crear_clip_persistible' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:1464` | long_params | 4 | función '_renderizar_clips' con 7 parámetros |
| `backend_fastapi/app/routers/jobs.py:1520` | long_function | 4 | función '_completar_job_exitoso' de 31 líneas |
| `backend_fastapi/app/routers/jobs.py:1520` | long_params | 4 | función '_completar_job_exitoso' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:1597` | long_params | 4 | función '_mensaje_por_causa_comun' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1619` | long_params | 4 | función '_guardar_metadata_detallada' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:1637` | long_params | 4 | función '_persistir_metadata_fallo' con 5 parámetros |
| `backend_fastapi/app/routers/jobs.py:1661` | long_params | 4 | función '_marcar_failed_descriptivo' con 6 parámetros |
| `backend_fastapi/app/routers/jobs.py:1677` | long_params | 4 | función '_aplicar_mensaje_failed' con 7 parámetros |
| `backend_fastapi/app/routers/publish.py:35` | long_params | 4 | función 'publish_clip' con 5 parámetros |
| `backend_fastapi/app/routers/publish.py:185` | long_function | 4 | función 'publish_stream' de 38 líneas |
| `backend_fastapi/app/routers/sample.py:79` | long_function | 4 | función 'create_sample_job' de 59 líneas |
| `backend_fastapi/app/routers/social_auth.py:241` | long_params | 4 | función '_redirect_oauth' con 5 parámetros |
| `backend_fastapi/app/routers/social_auth.py:268` | long_params | 4 | función 'youtube_callback' con 5 parámetros |
| `backend_fastapi/app/routers/social_auth.py:340` | long_params | 4 | función 'instagram_callback' con 5 parámetros |
| `backend_fastapi/app/routers/social_auth.py:462` | long_params | 4 | función 'tiktok_callback' con 5 parámetros |
| `backend_fastapi/app/routers/stream.py:143` | long_params | 4 | función '_eventos_iteracion' con 5 parámetros |
| `backend_fastapi/app/security/jwt.py:24` | long_function | 4 | función 'create_access_token' de 32 líneas |
| `backend_fastapi/app/services/ass_generator.py:68` | long_params | 4 | función '_cortar_linea' con 6 parámetros |
| `backend_fastapi/app/services/ass_generator.py:100` | long_params | 4 | función 'generate_ass_content' con 6 parámetros |
| `backend_fastapi/app/services/ass_generator.py:235` | long_params | 4 | función '_seg_del_rango' con 6 parámetros |
| `backend_fastapi/app/services/ass_generator.py:246` | long_params | 4 | función '_segs_de_segmento' con 7 parámetros |
| `backend_fastapi/app/services/ass_generator.py:268` | long_params | 4 | función '_generate_hooked_segments' con 5 parámetros |
| `backend_fastapi/app/services/ass_generator.py:295` | long_params | 4 | función 'generate_hooked_ass' con 7 parámetros |
| `backend_fastapi/app/services/ass_generator.py:309` | long_params | 4 | función 'build_hooked_ass_content' con 6 parámetros |
| `backend_fastapi/app/services/claude_service.py:171` | long_function | 4 | función '_build_output_schema' de 51 líneas |
| `backend_fastapi/app/services/claude_service.py:232` | long_function | 4 | función '_build_claude_prompt' de 44 líneas |
| `backend_fastapi/app/services/claude_service.py:314` | long_params | 4 | función '_llamar_sdk_anthropic' con 5 parámetros |
| `backend_fastapi/app/services/claude_service.py:509` | long_params | 4 | función '_pedir_con_requests' con 5 parámetros |
| `backend_fastapi/app/services/claude_service.py:614` | long_params | 4 | función '_formato_de_clip_valido' con 5 parámetros |
| `backend_fastapi/app/services/editor.py:64` | long_function | 4 | función '_comando_reframe' de 32 líneas |
| `backend_fastapi/app/services/engine.py:150` | long_params | 4 | función '_evaluar_ventana' con 5 parámetros |
| `backend_fastapi/app/services/engine.py:168` | long_params | 4 | función '_ventana_frontier' con 5 parámetros |
| `backend_fastapi/app/services/engine.py:306` | long_function | 4 | función '_hook_desde_candidato' de 35 líneas |
| `backend_fastapi/app/services/engine.py:306` | long_params | 4 | función '_hook_desde_candidato' con 5 parámetros |
| `backend_fastapi/app/services/engine.py:343` | long_function | 4 | función '_select_clip_hook' de 31 líneas |
| `backend_fastapi/app/services/engine.py:916` | long_function | 4 | función '_mapear_clip_claude' de 38 líneas |
| `backend_fastapi/app/services/ffmpeg_service.py:105` | long_function | 4 | función 'burn_subtitles' de 47 líneas |
| `backend_fastapi/app/services/ffmpeg_service.py:105` | long_params | 4 | función 'burn_subtitles' con 7 parámetros |
| `backend_fastapi/app/services/ffmpeg_service.py:197` | long_params | 4 | función 'cut_segment' con 6 parámetros |
| `backend_fastapi/app/services/ffmpeg_service.py:372` | long_params | 4 | función '_ensamblar_hook' con 6 parámetros |
| `backend_fastapi/app/services/ffmpeg_service.py:400` | long_function | 4 | función 'build_hook_clip' de 34 líneas |
| `backend_fastapi/app/services/ffmpeg_service.py:400` | long_params | 4 | función 'build_hook_clip' con 7 parámetros |
| `backend_fastapi/app/services/hook_service.py:108` | long_function | 4 | función '_build_hook_prompt' de 58 líneas |
| `backend_fastapi/app/services/hook_service.py:187` | long_params | 4 | función '_post_with_retry' con 5 parámetros |
| `backend_fastapi/app/services/hook_service.py:302` | long_params | 4 | función '_clip_llm_valido' con 6 parámetros |
| `backend_fastapi/app/services/instagram_service.py:365` | long_params | 4 | función '_actualizar_cuenta_ig' con 7 parámetros |
| `backend_fastapi/app/services/instagram_service.py:381` | long_params | 4 | función '_cuenta_nueva_ig' con 7 parámetros |
| `backend_fastapi/app/services/publish_service.py:599` | long_function | 4 | función '_publicar_upload_youtube' de 30 líneas |
| `backend_fastapi/app/services/publish_service.py:1029` | long_function | 4 | función '_iniciar_upload_tiktok' de 48 líneas |
| `backend_fastapi/app/services/publish_service.py:1314` | long_params | 4 | función '_publicar_via_webhook' con 5 parámetros |
| `backend_fastapi/app/services/publish_service.py:1345` | long_params | 4 | función '_do_publish' con 5 parámetros |
| `backend_fastapi/app/services/publish_service.py:1383` | long_params | 4 | función '_reintentar_publicacion' con 6 parámetros |
| `backend_fastapi/app/services/publish_service.py:1406` | long_params | 4 | función '_reintentar_tras_refresh' con 7 parámetros |
| `backend_fastapi/app/services/publish_service.py:1427` | long_params | 4 | función '_reaccionar_token_expirado' con 7 parámetros |
| `backend_fastapi/app/services/publish_service.py:1439` | long_params | 4 | función '_publicar_con_oauth' con 6 parámetros |
| `backend_fastapi/app/services/publish_service.py:1461` | long_params | 4 | función '_webhook_o_falso' con 6 parámetros |
| `backend_fastapi/app/services/publish_service.py:1470` | long_params | 4 | función '_resultado_publicacion' con 8 parámetros |
| `backend_fastapi/app/services/publish_service.py:1496` | long_params | 4 | función '_persistir_publicado' con 5 parámetros |
| `backend_fastapi/app/services/publish_service.py:1522` | long_params | 4 | función '_publicar_y_persistir' con 6 parámetros |
| `backend_fastapi/app/services/publish_service.py:1557` | long_params | 4 | función 'publish_clip_task' con 5 parámetros |
| `backend_fastapi/app/services/runpod_service.py:126` | long_function | 4 | función 'process_local_video_via_runpod' de 37 líneas |
| `backend_fastapi/app/services/runpod_service.py:380` | long_params | 4 | función '_esperar_job' con 6 parámetros |
| `backend_fastapi/app/services/runpod_service.py:400` | long_function | 4 | función 'process_video_via_runpod' de 32 líneas |
| `backend_fastapi/app/services/storage_cleanup.py:140` | long_function | 4 | función 'cleanup_storage' de 41 líneas |
| `backend_fastapi/app/services/storage_cleanup.py:183` | long_function | 4 | función 'ensure_disk_space' de 34 líneas |
| `backend_fastapi/app/services/tiktok_service.py:292` | long_params | 4 | función '_actualizar_cuenta' con 7 parámetros |
| `backend_fastapi/app/services/tiktok_service.py:318` | long_params | 4 | función '_crear_cuenta_tiktok' con 7 parámetros |
| `backend_fastapi/app/services/transcript_utils.py:16` | long_function | 4 | función 'parse_transcript_text_to_segments' de 55 líneas |
| `backend_fastapi/app/services/youtube_service.py:208` | long_params | 4 | función '_actualizar_cuenta_youtube' con 8 parámetros |
| `backend_fastapi/app/services/youtube_service.py:236` | long_params | 4 | función '_crear_cuenta_youtube' con 7 parámetros |
| `backend_fastapi/app/tasks/subtitle_pipeline.py:123` | long_params | 4 | función '_update_clip_status' con 5 parámetros |
| `editor_viral.py:44` | long_function | 4 | función 'calcular_filtro_vertical' de 40 líneas |
| `ejemplo_engine.py:25` | long_function | 4 | función 'main' de 44 líneas |
| `engine.py:423` | long_function | 4 | función '_paso_generar_archivos' de 30 líneas |
| `engine.py:473` | long_function | 4 | función '_ejecutar_pipeline_interno' de 32 líneas |
| `engine.py:507` | long_function | 4 | función 'procesar_video' de 72 líneas |
| `engine_subprocess.py:116` | long_function | 4 | función 'procesar_video_subprocess' de 41 líneas |
| `frontend_react/src/components/Avatar.tsx:42` | long_params | 4 | función 'Avatar' con 5 parámetros |
| `frontend_react/src/components/Footer.tsx:1` | long_function | 4 | función 'Footer' de 39 líneas |
| `frontend_react/src/components/auth/AuthForm.tsx:21` | long_function | 4 | función 'AuthForm' de 99 líneas |
| `frontend_react/src/components/auth/AuthProvider.tsx:31` | long_function | 4 | función 'useEffect' de 59 líneas |
| `frontend_react/src/components/clip-library/ClipCard.tsx:17` | long_function | 4 | función 'ClipCard' de 79 líneas |
| `frontend_react/src/components/clip-library/ClipResults.tsx:73` | long_function | 4 | función 'ClipResults' de 114 líneas |
| `frontend_react/src/components/clip-library/FilterBar.tsx:16` | long_function | 4 | función 'FilterBar' de 48 líneas |
| `frontend_react/src/components/clip-library/PublishDialog.tsx:18` | long_function | 4 | función 'PublishDialog' de 42 líneas |
| `frontend_react/src/components/dashboard/DashboardContent.tsx:9` | long_function | 4 | función 'DashboardContent' de 93 líneas |
| `frontend_react/src/components/dashboard/KpiGrid.tsx:8` | long_function | 4 | función 'KpiGrid' de 62 líneas |
| `frontend_react/src/components/integrations/PlatformCard.tsx:20` | long_function | 4 | función 'PlatformCard' de 38 líneas |
| `frontend_react/src/components/job-status/CompletedClips.tsx:11` | long_function | 4 | función 'CompletedClips' de 81 líneas |
| `frontend_react/src/components/job-status/JobProgress.tsx:7` | long_function | 4 | función 'JobProgress' de 40 líneas |
| `frontend_react/src/components/landing/LandingAbout.tsx:4` | long_function | 4 | función 'LandingAbout' de 37 líneas |
| `frontend_react/src/components/landing/LandingFeatures.tsx:4` | long_function | 4 | función 'LandingFeatures' de 31 líneas |
| `frontend_react/src/components/landing/LandingFooter.tsx:34` | long_function | 4 | función 'LandingFooter' de 46 líneas |
| `frontend_react/src/components/landing/LandingHero.tsx:14` | long_function | 4 | función 'LandingHero' de 76 líneas |
| `frontend_react/src/components/landing/LandingHowItWorks.tsx:5` | long_function | 4 | función 'LandingHowItWorks' de 105 líneas |
| `frontend_react/src/components/navbar/QuickCreateDropdown.tsx:4` | long_function | 4 | función 'QuickCreateDropdown' de 38 líneas |
| `frontend_react/src/components/settings/SettingsForms.tsx:31` | long_function | 4 | función 'SettingsForms' de 93 líneas |
| `frontend_react/src/components/upload/DirectUploadPanel.tsx:11` | long_function | 4 | función 'DirectUploadPanel' de 51 líneas |
| `frontend_react/src/components/upload/Dropzone.tsx:12` | long_function | 4 | función 'Dropzone' de 33 líneas |
| `frontend_react/src/hooks/useIntegrations.ts:59` | long_function | 4 | función 'useIntegrations' de 65 líneas |
| `frontend_react/src/hooks/useJobPolling.ts:120` | long_function | 4 | función 'useJobPolling' de 61 líneas |
| `frontend_react/src/hooks/usePublishSSE.ts:67` | long_function | 4 | función 'applySseStatus' de 78 líneas |
| `frontend_react/src/hooks/usePublishSSE.ts:68` | long_function | 4 | función 'applySseFields' de 77 líneas |
| `frontend_react/src/hooks/usePublishSSE.ts:71` | long_function | 4 | función 'usePublishSSE' de 75 líneas |
| `frontend_react/src/hooks/usePublishSSE.ts:78` | long_function | 4 | función 'useEffect' de 61 líneas |
| `frontend_react/src/hooks/useUploadAndProcess.ts:117` | long_function | 4 | función 'useUploadAndProcess' de 37 líneas |
| `frontend_react/src/pages/AuthPage.tsx:29` | long_function | 4 | función 'AuthPage' de 61 líneas |
| `frontend_react/src/pages/ClipLibraryPage.tsx:24` | long_function | 4 | función 'ClipLibraryPage' de 114 líneas |
| `frontend_react/src/pages/DashboardPage.tsx:226` | long_params | 4 | función 'renderDayBar' con 5 parámetros |
| `frontend_react/src/pages/DashboardPage.tsx:278` | long_function | 4 | función 'renderMetricsBody' de 67 líneas |
| `frontend_react/src/pages/DashboardPage.tsx:351` | long_function | 4 | función 'DashboardPage' de 107 líneas |
| `frontend_react/src/pages/IntegrationsPage.tsx:88` | long_function | 4 | función 'IntegrationsPage' de 89 líneas |
| `frontend_react/src/pages/JobStatusPage.tsx:119` | long_function | 4 | función 'JobStatusPage' de 84 líneas |
| `frontend_react/src/pages/LandingPage.tsx:19` | long_function | 4 | función 'LandingPage' de 41 líneas |
| `frontend_react/src/pages/SettingsPage.tsx:88` | long_function | 4 | función 'SettingsPage' de 96 líneas |
| `frontend_react/src/pages/UploadPage.tsx:77` | long_function | 4 | función 'UploadPage' de 109 líneas |
| `frontend_react/src/pages/legal/DataDeletionPage.tsx:4` | long_function | 4 | función 'DataDeletionPage' de 67 líneas |
| `frontend_react/src/pages/legal/PrivacyPage.tsx:4` | long_function | 4 | función 'PrivacyPage' de 82 líneas |
| `frontend_react/src/pages/legal/TermsPage.tsx:4` | long_function | 4 | función 'TermsPage' de 85 líneas |
| `frontend_vue/src/composables/useClipLibrary.ts:8` | long_function | 4 | función 'useClipLibrary' de 269 líneas |
| `frontend_vue/src/composables/useClipLibrary.ts:182` | long_params | 4 | función 'watch' con 6 parámetros |
| `frontend_vue/src/composables/useIntegrations.ts:38` | long_function | 4 | función 'useIntegrations' de 118 líneas |
| `frontend_vue/src/composables/useJobPolling.ts:59` | long_function | 4 | función 'handleUnrecoverablePollFailure' de 45 líneas |
| `frontend_vue/src/composables/useJobPolling.ts:94` | long_function | 4 | función 'useJobPolling' de 55 líneas |
| `frontend_vue/src/composables/usePublishStream.ts:63` | long_function | 4 | función 'usePublishStream' de 64 líneas |
| `frontend_vue/src/stores/auth.ts:45` | long_function | 4 | función 'init' de 44 líneas |
| `frontend_vue/src/views/SettingsView.vue:116` | long_params | 4 | función 'applyFetchedProfile' con 5 parámetros |
| `main.py:207` | long_params | 4 | función '_integrar_linea_transcripcion' con 5 parámetros |
| `main.py:449` | long_function | 4 | función 'construir_prompt' de 116 líneas |
| `main.py:576` | long_params | 4 | función '_post_con_retry' con 5 parámetros |
| `main.py:1031` | long_function | 4 | función '_clip_valido' de 35 líneas |
| `main.py:1158` | long_function | 4 | función 'procesar_clips' de 38 líneas |
| `main.py:1327` | long_params | 4 | función '_ejecutar_pipeline_cli' con 5 parámetros |
| `scripts/make_og_image.py:37` | long_params | 4 | función 'glow' con 5 parámetros |
| `video_processor.py:20` | long_function | 4 | función 'generate_ass_from_segments' de 55 líneas |
| `video_processor.py:20` | long_params | 4 | función 'generate_ass_from_segments' con 6 parámetros |
| `video_processor.py:108` | long_params | 4 | función '_segmento_aplicable' con 5 parámetros |
| `video_processor.py:335` | long_function | 4 | función 'reframe_and_burn_subtitles' de 52 líneas |
| `video_processor.py:335` | long_params | 4 | función 'reframe_and_burn_subtitles' con 6 parámetros |
| `video_processor.py:389` | long_function | 4 | función 'process_clip_vertical' de 60 líneas |
| `video_processor.py:389` | long_params | 4 | función 'process_clip_vertical' con 6 parámetros |
| `whisper_transcriber.py:152` | long_params | 4 | función '_abrir_segmento_ts' con 5 parámetros |
| `whisper_transcriber.py:222` | long_function | 4 | función 'parsear_transcripcion_youtube' de 34 líneas |
| `whisper_transcriber.py:288` | long_function | 4 | función '_transcribir_segmentos' de 53 líneas |
| `whisper_transcriber.py:370` | long_function | 4 | función 'transcribir_video' de 34 líneas |

**Componente demasiado grande (BigC)** — 8 hallazgo(s) en 8 archivo(s):

| Archivo | Línea(s) | Señal | Detalle |
|---|---|---|---|
| `frontend_react/src/components/clip-library/ClipResults.tsx` | 1 | big_component | componente grande (180 líneas) |
| `frontend_react/src/pages/DashboardPage.tsx` | 1 | big_component | componente grande (428 líneas) |
| `frontend_react/src/pages/IntegrationsPage.tsx` | 1 | big_component | componente grande (164 líneas) |
| `frontend_react/src/pages/JobStatusPage.tsx` | 1 | big_component | componente grande (182 líneas) |
| `frontend_react/src/pages/SettingsPage.tsx` | 1 | big_component | componente grande (168 líneas) |
| `frontend_react/src/pages/UploadPage.tsx` | 1 | big_component | componente grande (173 líneas) |
| `frontend_vue/src/views/JobStatusView.vue` | 1 | big_component | componente grande (156 líneas) |
| `frontend_vue/src/views/SettingsView.vue` | 1 | big_component | componente grande (171 líneas) |

**Cobertura (Cob)** — unidades por debajo del umbral:

| Unidad | Cobertura | Líneas cubiertas / totales |
|---|---:|---:|
| `.` | 75.5% | 8567/11353 |
| `backend_fastapi` | 79.0% | 6430/8140 |

---
_Informe generado por la cátedra. Los umbrales corresponden al perfil `exigente`. Ante dudas, revisá el archivo y la línea señalados y el criterio en `CRITERIOS-CALIDAD.md`._
<!-- evaluacion:fin -->
