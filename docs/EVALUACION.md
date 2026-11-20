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

Se listan los archivos y líneas que el análisis marca para cada criterio en rojo. Para **duplicación** se muestran los archivos con más líneas repetidas; para **cobertura**, las unidades por debajo del umbral.

**Índice (indice)** — señales que más pesan:

- `editor_viral.py:112` — high_coupling: clase 'RenderizadorVertical' muy acoplada (CBO=11)
- `editor_viral.py:193` — high_coupling: clase 'VideoEditor' muy acoplada (CBO=21)
- `editor_viral.py:44` — long_function: función 'calcular_filtro_vertical' de 40 líneas
- `main.py:118` — high_complexity: función '_agregar_momentos_cluster' con complejidad 6
- `main.py:207` — long_params: función '_integrar_linea_transcripcion' con 5 parámetros
- `main.py:449` — long_function: función 'construir_prompt' de 116 líneas
- `main.py:576` — long_params: función '_post_con_retry' con 5 parámetros
- `main.py:1031` — long_function: función '_clip_valido' de 35 líneas
- `main.py:1158` — long_function: función 'procesar_clips' de 38 líneas
- `main.py:1327` — long_params: función '_ejecutar_pipeline_cli' con 5 parámetros
- `whisper_transcriber.py:152` — long_params: función '_abrir_segmento_ts' con 5 parámetros
- `whisper_transcriber.py:222` — long_function: función 'parsear_transcripcion_youtube' de 34 líneas
- `whisper_transcriber.py:288` — long_function: función '_transcribir_segmentos' de 53 líneas
- `whisper_transcriber.py:370` — long_function: función 'transcribir_video' de 34 líneas
- `audio_analyzer.py:61` — long_params: función '_agregar_evento_nivel' con 5 parámetros
- `audio_analyzer.py:81` — long_params: función '_agregar_cambio_brusco' con 6 parámetros
- `audio_analyzer.py:330` — long_function: función 'analizar_audio' de 50 líneas
- `ejemplo_engine.py:25` — long_function: función 'main' de 44 líneas
- `ejemplo_engine.py:25` — high_complexity: función 'main' con complejidad 13
- `video_processor.py:20` — long_function: función 'generate_ass_from_segments' de 55 líneas
- `video_processor.py:20` — long_params: función 'generate_ass_from_segments' con 6 parámetros
- `video_processor.py:108` — long_params: función '_segmento_aplicable' con 5 parámetros
- `video_processor.py:335` — long_function: función 'reframe_and_burn_subtitles' de 52 líneas
- `video_processor.py:335` — long_params: función 'reframe_and_burn_subtitles' con 6 parámetros
- `video_processor.py:389` — long_function: función 'process_clip_vertical' de 60 líneas
- `video_processor.py:389` — long_params: función 'process_clip_vertical' con 6 parámetros
- `engine_subprocess.py:116` — long_function: función 'procesar_video_subprocess' de 41 líneas
- `engine.py:423` — long_function: función '_paso_generar_archivos' de 30 líneas
- `engine.py:473` — long_function: función '_ejecutar_pipeline_interno' de 32 líneas
- `engine.py:507` — long_function: función 'procesar_video' de 72 líneas
- … y 263 hallazgo(s) más.

**Componente demasiado grande (BigC)** — 8 hallazgo(s) en 8 archivo(s):

| Archivo | Línea(s) | Señal |
|---|---|---|
| `frontend_react/src/components/clip-library/ClipResults.tsx` | 1 | componente grande (180 líneas) |
| `frontend_react/src/pages/DashboardPage.tsx` | 1 | componente grande (428 líneas) |
| `frontend_react/src/pages/IntegrationsPage.tsx` | 1 | componente grande (164 líneas) |
| `frontend_react/src/pages/JobStatusPage.tsx` | 1 | componente grande (182 líneas) |
| `frontend_react/src/pages/SettingsPage.tsx` | 1 | componente grande (168 líneas) |
| `frontend_react/src/pages/UploadPage.tsx` | 1 | componente grande (173 líneas) |
| `frontend_vue/src/views/JobStatusView.vue` | 1 | componente grande (156 líneas) |
| `frontend_vue/src/views/SettingsView.vue` | 1 | componente grande (171 líneas) |

**Cobertura (Cob)** — unidades por debajo del umbral:

- `.` — 75.5% (8567/11353 líneas)
- `backend_fastapi` — 79.0% (6430/8140 líneas)

---
_Informe generado por la cátedra. Los umbrales corresponden al perfil `exigente`. Ante dudas, revisá el archivo y la línea señalados y el criterio en `CRITERIOS-CALIDAD.md`._
<!-- evaluacion:fin -->
