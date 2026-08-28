# Engine clipsai - Guía de Uso e Integración

## Resumen

El módulo `engine.py` envuelve el pipeline completo de clipsai (extracción de audio, análisis, IA, corte de clips) en una **única función invocable** con firma simplificada y **manejo de errores estructurado**.

```python
from engine import procesar_video

resultado = procesar_video("video.mp4", "transcripcion.txt")
```

---

## Interfaz Pública

### Función Principal

```python
procesar_video(video_path: str, transcripcion_path: str) -> ProcesamientoResultado
```

**Parámetros:**
- `video_path`: Ruta al archivo de video (mp4, mov, mkv, webm, etc.)
- `transcripcion_path`: Ruta al archivo de transcripción en **formato YouTube crudo**

**Formato de transcripción esperado:**
```
0:00 - Primer segmento de texto
0:30 - Segundo segmento con timestamp
1:00 - Tercer segmento
...
```

### Resultado Estructurado

```python
@dataclass
class ProcesamientoResultado:
    exito: bool                    # True si todo OK, False si error
    clips: List[ClipInfo]          # Lista de clips generados (vacía si error)
    carpeta_salida: str            # Ruta absoluta a la carpeta con los clips
    error: Optional[str]           # Mensaje de error legible (None si éxito)
    error_tipo: Optional[str]      # Categoría de error para manejo programático
    error_detalle: Optional[str]   # Traceback técnico para depuración
```

```python
@dataclass
class ClipInfo:
    archivo: str                   # Ruta absoluta al archivo .mp4 generado
    inicio: str                    # Timestamp inicio HH:MM:SS
    fin: str                       # Timestamp fin HH:MM:SS
    titulo_sugerido: str           # Título sugerido para el clip
    hook_texto: str                # Texto del gancho inicial (2-5 palabras)
    criterio_principal: str        # revelacion|controversia|dato_impactante|emocional|analisis_tactico|prediccion
    score: int                     # Score viralidad 1-10
    primer_segundo: str            # Primeras palabras exactas del clip
    motivo: str                    # Explicación de por qué es viral
```

---

## Ejemplos de Uso

### 1. Uso Básico (Programático)

```python
from engine import procesar_video

resultado = procesar_video("mi_video.mp4", "transcripcion.txt")

if resultado.exito:
    print(f"✓ {len(resultado.clips)} clips generados en {resultado.carpeta_salida}")
    for clip in resultado.clips:
        print(f"  - {clip.archivo} ({clip.inicio}-{clip.fin}) Score: {clip.score}")
else:
    print(f"✗ Error [{resultado.error_tipo}]: {resultado.error}")
    if resultado.error_detalle:
        print(f"  Detalle: {resultado.error_detalle}")
```

### 2. Integración en API Web (FastAPI/Express)

```python
# FastAPI endpoint
@app.post("/api/videos/{video_id}/procesar")
async def procesar_video_endpoint(video_id: str, transcripcion: UploadFile):
    # Guardar archivos temporales...
    resultado = procesar_video(video_path, transcripcion_path)
    
    if resultado.exito:
        return {
            "success": True,
            "clips": [c.__dict__ for c in resultado.clips],
            "carpeta_salida": resultado.carpeta_salida
        }
    else:
        # Mapear error_tipo a código HTTP apropiado
        codigos = {
            "ValidacionError": 400,
            "ConexionError": 502,
            "TimeoutError": 504,
            "IAError": 502,
            "AudioError": 500,
            "TranscripcionError": 400,
            "GeneracionError": 500,
            "SinClipsValidos": 422,
        }
        raise HTTPException(
            status_code=codigos.get(resultado.error_tipo, 500),
            detail={
                "error": resultado.error,
                "tipo": resultado.error_tipo,
                "detalle": resultado.error_detalle
            }
        )
```

### 3. CLI Directo (Testing)

```bash
# Salida legible
python engine.py video.mp4 transcripcion.txt

# Salida JSON (para parsing automático)
python engine.py video.mp4 transcripcion.txt --json

# Sin limpiar directorio temporal
python engine.py video.mp4 transcripcion.txt --no-cleanup
```

### 4. Wrapper por Subprocess (Aislamiento total)

```python
from engine_subprocess import procesar_video_subprocess

resultado = procesar_video_subprocess(
    "video.mp4", 
    "transcripcion.txt",
    timeout_segundos=600,      # 10 min máximo
    python_executable="python3"
)
```

---

## Tipos de Error y Manejo

| `error_tipo` | Causa | Acción Recomendada |
|--------------|-------|-------------------|
| `ValidacionError` | Archivos no existen o sin permisos | Verificar rutas y permisos (HTTP 400) |
| `DependenciaError` | FFmpeg no instalado | Instalar FFmpeg en el servidor |
| `ImportError` | Falta librosa, faster-whisper, etc. | `pip install -r requirements.txt` |
| `AudioError` | Falló extracción de audio | Verificar codec del video |
| `TranscripcionError` | Formato inválido | Validar formato YouTube antes de enviar |
| `PreparacionIAError` | Error preparando prompt | Revisar logs, transcripción muy larga |
| `ConexionError` | API key inválida / sin red | Verificar ANTHROPIC_API_KEY / OPENAI_API_KEY |
| `TimeoutError` | IA tardó demasiado | Aumentar timeout o reintentar |
| `IAError` | Respuesta IA inválida | Reintentar, puede ser rate limit |
| `GeneracionError` | Falló FFmpeg al cortar | Verificar espacio en disco, codecs |
| `SinClipsValidos` | IA no encontró clips válidos | Video muy corto / sin contenido viral |
| `ErrorInterno` | Bug no capturado | Reportar con `error_detalle` |

---

## Limpieza de Recursos

Los clips se generan en un directorio temporal (`/tmp/clipsai_XXXXXX/clips/`).
**El caller es responsable de mover/limpiar los archivos.**

```python
from engine import limpiar_directorio_trabajo

resultado = procesar_video(video, transcripcion)
if resultado.exito:
    # Mover clips a almacenamiento permanente...
    for clip in resultado.clips:
        shutil.move(clip.archivo, f"/storage/clips/{os.path.basename(clip.archivo)}")
    
    # Limpiar temporal
    limpiar_directorio_trabajo(resultado.carpeta_salida)
```

---

## Dependencias Requeridas

```bash
# Sistema
ffmpeg

# Python (requirements.txt)
anthropic>=0.25.0
requests
pydub
faster-whisper
librosa
scikit-learn
numpy
opencv-python  # para editor_viral.py (opcional)
```

---

## Pruebas de Verificación

```bash
# 1. Importación básica
python3 -c "from engine import procesar_video; print('OK')"

# 2. Validación de archivos inexistentes
python3 -c "
from engine import procesar_video
r = procesar_video('no.mp4', 'no.txt')
assert not r.exito
assert r.error_tipo == 'ValidacionError'
print('Validación OK')
"

# 3. Serialización JSON
python3 -c "
from engine import ProcesamientoResultado
r = ProcesamientoResultado.exito_resultado([], '/tmp/x')
print(r.to_dict())
"

# 4. Ejemplo completo (requiere API key válida)
python3 ejemplo_engine.py video.mp4 transcripcion.txt
```

---

## Evidencia de Cumplimiento - Issue 2

### ✅ Criterio 1: Único punto de entrada con video + transcripción
```python
resultado = procesar_video("video.mp4", "transcripcion.txt")
# Una sola función, dos parámetros, nada más
```

### ✅ Criterio 2: Errores estructurados (no crash sin info)
```python
# SIEMPRE devuelve ProcesamientoResultado, nunca hace sys.exit()
# Ni lanza excepciones no capturadas
{
  "exito": false,
  "error": "Error de conexión con API de IA: Error 401...",
  "error_tipo": "ConexionError",
  "error_detalle": "Traceback (most recent call last)..."
}
```

### ✅ Sin lógica de tipos de contenido / multi-cámara
El engine usa exclusivamente el flujo estandarizado que ya funcionaba en `main.py`.

### ✅ Desacoplado de la capa web
- No importa frameworks web (FastAPI, Express, etc.)
- No usa variables globales de configuración web
- Solo requiere: video path + transcripción path
- Devuelve: estructura de datos pura (dataclasses → JSON)

---

## Archivos Entregados

| Archivo | Descripción |
|---------|-------------|
| `engine.py` | **Wrapper principal** - importación directa, API síncrona |
| `engine_subprocess.py` | Wrapper alternativo por subprocess (aislamiento) |
| `ejemplo_engine.py` | Ejemplo completo de integración |
| `ENGINE_USO.md` | Esta documentación |