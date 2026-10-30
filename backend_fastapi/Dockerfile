# syntax=docker/dockerfile:1
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HUGGINGFACE_HUB_CACHE=/app/whisper_model

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar curl si no está disponible
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Descargar FFmpeg estático con todos los codecs (incluido libx264)
RUN curl -sSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg-release.tar.xz \
    && tar -xf ffmpeg-release.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-release.tar.xz ffmpeg-*-amd64-static \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Asegurar que /usr/local/bin esté primero en el PATH
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"

# Verificar que ffmpeg tenga libx264
RUN /usr/local/bin/ffmpeg -encoders 2>/dev/null | grep libx264 || (echo "ERROR: libx264 no disponible" && exit 1)

# Verificar versiones y entorno
RUN python --version \
    && python -c "import torch; print(f'PyTorch {torch.__version__} con CUDA {torch.version.cuda}')" \
    && /usr/local/bin/ffmpeg -version \
    && /usr/local/bin/ffprobe -version

# Instalar dependencias de Python
COPY backend_fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# El modelo Whisper se descarga en el primer arranque del worker (evita corrupción en build)

# Copiar código
COPY backend_fastapi/app ./app
# Embebido: engine.py
COPY <<'ENGINE_PY_EOF' ./engine.py
#!/usr/bin/env python3
"""
Wrapper estable para el motor de clipsai.

Provee una interfaz simple y clara para invocar el pipeline completo:
    procesar_video(video_path, transcripcion_path) -> ProcesamientoResultado

No modifica la lógica interna del pipeline; solo la envuelve y estandariza
la entrada/salida y el manejo de errores.
"""

import os
import sys
import json
import traceback
import tempfile
import shutil
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class ClipInfo:
    """Información de un clip generado."""
    archivo: str
    inicio: str
    fin: str
    titulo_sugerido: str
    hook_texto: str
    criterio_principal: str
    score: int
    primer_segundo: str
    motivo: str


@dataclass
class ProcesamientoResultado:
    """Resultado estructurado del procesamiento."""
    exito: bool
    clips: List[ClipInfo]
    carpeta_salida: str
    error: Optional[str] = None
    error_tipo: Optional[str] = None
    error_detalle: Optional[str] = None
    transcription_segments: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el resultado a diccionario para serialización JSON."""
        return {
            "exito": self.exito,
            "clips": [asdict(c) for c in self.clips],
            "carpeta_salida": self.carpeta_salida,
            "error": self.error,
            "error_tipo": self.error_tipo,
            "error_detalle": self.error_detalle,
            "transcription_segments": self.transcription_segments or [],
        }

    @classmethod
    def exito_resultado(cls, clips: List[ClipInfo], carpeta_salida: str, transcription_segments: Optional[List[Dict[str, Any]]] = None) -> "ProcesamientoResultado":
        """Factory para resultado exitoso."""
        return cls(exito=True, clips=clips, carpeta_salida=carpeta_salida, transcription_segments=transcription_segments)

    @classmethod
    def error_resultado(cls, error: str, error_tipo: str = "Error", error_detalle: str = "") -> "ProcesamientoResultado":
        """Factory para resultado de error."""
        return cls(
            exito=False,
            clips=[],
            carpeta_salida="",
            error=error,
            error_tipo=error_tipo,
            error_detalle=error_detalle,
        )


def _validar_entradas(video_path: str, transcripcion_path: str) -> Optional[str]:
    """Valida que las entradas existan y sean accesibles. Retorna mensaje de error o None."""
    if not os.path.exists(video_path):
        return f"Archivo de video no encontrado: {video_path}"
    if not os.path.exists(transcripcion_path):
        return f"Archivo de transcripción no encontrado: {transcripcion_path}"
    if not os.access(video_path, os.R_OK):
        return f"Sin permisos de lectura en video: {video_path}"
    if not os.access(transcripcion_path, os.R_OK):
        return f"Sin permisos de lectura en transcripción: {transcripcion_path}"
    return None


def _verificar_ffmpeg() -> bool:
    """Verifica si FFmpeg está instalado y accesible."""
    try:
        import subprocess
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def procesar_video(video_path: str, transcripcion_path: str) -> ProcesamientoResultado:
    """
    Procesa un video con su transcripción y genera clips virales.

    Esta es la ÚNICA función pública que debe invocarse desde la capa web.
    Envuelve todo el pipeline interno (extracción audio, análisis, IA, corte)
    y devuelve un resultado estructurado, nunca hace sys.exit() ni crashea.

    Args:
        video_path: Ruta absoluta o relativa al archivo de video (mp4, mov, etc.)
        transcripcion_path: Ruta absoluta o relativa al archivo de transcripción
                           en formato YouTube crudo (timestamps + texto)

    Returns:
        ProcesamientoResultado con:
        - exito=True: clips generados en carpeta_salida, lista de ClipInfo
        - exito=False: error, error_tipo, error_detalle con información de depuración

    Example:
        >>> resultado = procesar_video("video.mp4", "transcripcion.txt")
        >>> if resultado.exito:
        ...     for clip in resultado.clips:
        ...         print(f"Clip: {clip.archivo} ({clip.inicio}-{clip.fin})")
        ... else:
        ...     print(f"Error [{resultado.error_tipo}]: {resultado.error}")
        ...     if resultado.error_detalle:
        ...         print(f"Detalle: {resultado.error_detalle}")
    """
    # 1. Validaciones de entrada tempranas
    error_validacion = _validar_entradas(video_path, transcripcion_path)
    if error_validacion:
        return ProcesamientoResultado.error_resultado(
            error=error_validacion,
            error_tipo="ValidacionError",
            error_detalle=f"video_path={video_path}, transcripcion_path={transcripcion_path}"
        )

    if not _verificar_ffmpeg():
        return ProcesamientoResultado.error_resultado(
            error="FFmpeg no está instalado o no está en el PATH",
            error_tipo="DependenciaError",
            error_detalle="Instala FFmpeg: apt-get install ffmpeg / brew install ffmpeg / choco install ffmpeg"
        )

    # 2. Preparar entorno de trabajo aislado
    # Usamos un directorio temporal para no contaminar el workspace
    trabajo_dir = tempfile.mkdtemp(prefix="clipsai_")
    clips_dir = os.path.join(trabajo_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    # Guardar paths originales para el resultado
    video_original = os.path.abspath(video_path)
    transcripcion_original = os.path.abspath(transcripcion_path)

    try:
        # 3. Importar y ejecutar pipeline interno
        # Importamos aquí para que los errores de importación se capturen abajo
        from main import (
            extraer_audio,
            analizar_audio_video,
            leer_transcripcion_para_ia,
            formatear_transcripcion,
            preparar_transcripcion_para_ia,
            enriquecer_datos_para_ia,
            obtener_clips_ia,
            validar_clips,
            procesar_clips,
            AUDIO_ANALYZER_AVAILABLE,
        )
        from whisper_transcriber import parsear_transcripcion_youtube, transcribir_audio

        # 4. Ejecutar pipeline paso a paso con manejo de errores granular

        # 4.1 Extraer audio
        audio_path = os.path.join(trabajo_dir, "audio.mp3")
        try:
            extraer_audio(video_original, audio_path)
        except Exception as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Falló extracción de audio: {e}",
                error_tipo="AudioError",
                error_detalle=traceback.format_exc()
            )

        # 4.2 Analizar audio (opcional, continua si falla)
        datos_audio = []
        if AUDIO_ANALYZER_AVAILABLE:
            try:
                datos_audio = analizar_audio_video(audio_path)
            except Exception as e:
                # No es fatal, continuamos sin datos de audio
                datos_audio = []
        else:
            # audio_analyzer no disponible, continuamos
            pass

        # 4.3 Parsear transcripción o usar Whisper si está vacía
        transcripcion_formatted = os.path.join(trabajo_dir, "transcripcion_formatted.txt")
        
        # Primero intentar parsear la transcripción proporcionada
        print("[engine] Intentando parsear transcripción proporcionada...")
        try:
            parsear_transcripcion_youtube(transcripcion_original, transcripcion_formatted)
            
            # Verificar si se generaron segmentos válidos
            if os.path.exists(transcripcion_formatted):
                with open(transcripcion_formatted, 'r', encoding='utf-8') as f:
                    contenido = f.read().strip()
                
                if not contenido or len(contenido) < 10:
                    print(f"[engine] Transcripción vacía o muy corta ({len(contenido)} chars). Usando Whisper...")
                    raise ValueError("Transcripción vacía")
                
                # Contar líneas no vacías
                lineas = [l for l in contenido.split('\n') if l.strip()]
                if len(lineas) < 3:
                    print(f"[engine] Solo {len(lineas)} segmentos. Usando Whisper...")
                    raise ValueError("Muy pocos segmentos")
                
                print(f"[engine] Transcripción válida: {len(lineas)} segmentos")
            else:
                print(f"[engine] Archivo de transcripción no generado. Usando Whisper...")
                raise ValueError("Archivo no generado")
                
        except Exception as e:
            # Si falla el parseo o la transcripción está vacía, usar Whisper
            print(f"[engine] Parseo falló o transcripción vacía: {e}")
            print("[engine] Transcribiendo audio con Whisper...")
            try:
                # Transcribir audio directamente con Whisper
                transcribir_audio(audio_path, transcripcion_formatted)
                
                # Verificar resultado
                if not os.path.exists(transcripcion_formatted):
                    raise ValueError("Whisper no generó archivo de transcripción")
                
                with open(transcripcion_formatted, 'r', encoding='utf-8') as f:
                    contenido = f.read().strip()
                
                if not contenido:
                    raise ValueError("Whisper devolvió transcripción vacía")
                
                print(f"[engine] Whisper generó transcripción: {len(contenido)} chars")
                
            except Exception as whisper_err:
                return ProcesamientoResultado.error_resultado(
                    error=f"Falló transcripción con Whisper: {whisper_err}",
                    error_tipo="TranscripcionError",
                    error_detalle=traceback.format_exc()
                )

        # 4.4 Preparar datos para IA
        transcription_segments = []
        try:
            texto_para_ia = leer_transcripcion_para_ia(transcripcion_formatted)
            datos_enriquecidos = enriquecer_datos_para_ia(datos_audio, transcripcion_formatted)
            texto_para_ia = preparar_transcripcion_para_ia(transcripcion_formatted)
            
            # Leer segmentos de transcripción para incluirlos en el resultado
            # Formato esperado por jobs.py: {"start": float, "end": float, "text": str}
            try:
                with open(transcripcion_formatted, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if ' - ' in line:
                        parts = line.split(' - ', 1)
                        if len(parts) == 2:
                            timestamp_str, text = parts
                            if not text.strip():
                                continue
                            # Convertir timestamp M:SS, MM:SS o H:MM:SS a segundos
                            try:
                                ts_parts = timestamp_str.split(':')
                                if len(ts_parts) == 2:
                                    start_seconds = int(ts_parts[0]) * 60 + float(ts_parts[1])
                                elif len(ts_parts) == 3:
                                    start_seconds = int(ts_parts[0]) * 3600 + int(ts_parts[1]) * 60 + float(ts_parts[2])
                                else:
                                    start_seconds = float(timestamp_str)
                                
                                if start_seconds < 0:
                                    continue
                                
                                # Estimar end como start del siguiente segmento (o start + 3.0 para el último)
                                end_seconds = start_seconds + 3.0
                                if i + 1 < len(lines):
                                    next_line = lines[i + 1].strip()
                                    if ' - ' in next_line:
                                        next_parts = next_line.split(' - ', 1)
                                        if len(next_parts) == 2 and next_parts[0].strip():
                                            next_ts = next_parts[0].strip()
                                            next_ts_parts = next_ts.split(':')
                                            try:
                                                if len(next_ts_parts) == 2:
                                                    next_start = int(next_ts_parts[0]) * 60 + float(next_ts_parts[1])
                                                elif len(next_ts_parts) == 3:
                                                    next_start = int(next_ts_parts[0]) * 3600 + int(next_ts_parts[1]) * 60 + float(next_ts_parts[2])
                                                else:
                                                    next_start = float(next_ts)
                                                if next_start > start_seconds:
                                                    end_seconds = next_start
                                            except (ValueError, IndexError):
                                                pass
                                
                                transcription_segments.append({
                                    "start": round(start_seconds, 2),
                                    "end": round(end_seconds, 2),
                                    "text": text.strip()
                                })
                            except (ValueError, IndexError) as ts_err:
                                print(f"[engine] No se pudo parsear timestamp '{timestamp_str}': {ts_err}")
                
                # Log de los primeros 3 segmentos como muestra
                if transcription_segments:
                    print(f"[engine] Generados {len(transcription_segments)} segmentos de transcripción:")
                    for seg in transcription_segments[:3]:
                        print(f"  - start={seg['start']}, end={seg['end']}, text='{seg['text'][:50]}'")
                else:
                    print(f"[engine] WARNING: No se generaron segmentos de transcripción")
            except Exception as read_err:
                print(f"[engine] No se pudieron leer segmentos de transcripción: {read_err}")
        except Exception as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Falló preparación de datos para IA: {e}",
                error_tipo="PreparacionIAError",
                error_detalle=traceback.format_exc()
            )

        # 4.5 Obtener clips de la IA
        try:
            clips_ia = obtener_clips_ia(texto_para_ia, datos_audio, datos_enriquecidos)
        except ValueError as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Respuesta de IA inválida: {e}",
                error_tipo="IAError",
                error_detalle=traceback.format_exc()
            )
        except ConnectionError as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Error de conexión con API de IA: {e}",
                error_tipo="ConexionError",
                error_detalle=traceback.format_exc()
            )
        except TimeoutError as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Timeout consultando API de IA: {e}",
                error_tipo="TimeoutError",
                error_detalle=traceback.format_exc()
            )
        except Exception as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Error inesperado en IA: {e}",
                error_tipo="IAError",
                error_detalle=traceback.format_exc()
            )

        # 4.6 Validar clips
        clips_validos = validar_clips(clips_ia)
        if not clips_validos:
            # Respuesta válida pero vacía - no es un error, el video no tiene clips relevantes
            print(f"[engine] IA no encontró clips válidos (devolvió {len(clips_ia)} clips, ninguno pasó validación)")
            return ProcesamientoResultado.exito_resultado(
                clips=[],
                carpeta_salida=clips_dir,
                transcription_segments=transcription_segments
            )

        # 4.7 Generar clips de video
        try:
            archivos_generados = procesar_clips(video_original, clips_validos, clips_dir)
        except Exception as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Falló generación de clips de video: {e}",
                error_tipo="GeneracionError",
                error_detalle=traceback.format_exc()
            )

        if not archivos_generados:
            # Si no se generaron archivos, retornar éxito con 0 clips
            print(f"[engine] No se generaron archivos de clip, retornando resultado vacío")
            return ProcesamientoResultado.exito_resultado(
                clips=[],
                carpeta_salida=clips_dir,
                transcription_segments=transcription_segments
            )

        # 5. Leer info de clips generados desde clips_info.json
        clips_info_path = os.path.join(clips_dir, "clips_info.json")
        clips_resultado = []

        if os.path.exists(clips_info_path):
            with open(clips_info_path, "r", encoding="utf-8") as f:
                info_clips = json.load(f)

            for info in info_clips:
                clips_resultado.append(ClipInfo(
                    archivo=info.get("archivo", ""),
                    inicio=info.get("inicio", ""),
                    fin=info.get("fin", ""),
                    titulo_sugerido=info.get("titulo_sugerido", ""),
                    hook_texto=info.get("hook_texto", ""),
                    criterio_principal=info.get("criterio_principal", ""),
                    score=info.get("score", 0),
                    primer_segundo=info.get("primer_segundo", ""),
                    motivo=info.get("motivo", ""),
                ))

        # 6. Resultado exitoso
        return ProcesamientoResultado.exito_resultado(
            clips=clips_resultado,
            carpeta_salida=clips_dir,
            transcription_segments=transcription_segments
        )

    except ImportError as e:
        return ProcesamientoResultado.error_resultado(
            error=f"Dependencia faltante: {e}",
            error_tipo="ImportError",
            error_detalle=traceback.format_exc()
        )
    except Exception as e:
        return ProcesamientoResultado.error_resultado(
            error=f"Error interno inesperado: {e}",
            error_tipo="ErrorInterno",
            error_detalle=traceback.format_exc()
        )
    finally:
        # Nota: NO limpiamos el directorio temporal automáticamente
        # porque los clips generados están ahí y el caller puede querer moverlos.
        # El caller es responsable de limpiar o mover los archivos.
        pass


def limpiar_directorio_trabajo(carpeta_salida: str) -> bool:
    """
    Limpia el directorio de trabajo temporal.

    Args:
        carpeta_salida: Ruta devuelta en ProcesamientoResultado.carpeta_salida

    Returns:
        True si se limpió correctamente, False en caso contrario
    """
    try:
        trabajo_dir = os.path.dirname(carpeta_salida)
        if os.path.exists(trabajo_dir) and trabajo_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(trabajo_dir)
            return True
    except Exception:
        pass
    return False


# ============================================================
# CLI para testing directo del engine
# ============================================================

def _main_cli():
    """CLI simple para probar el engine directamente."""
    import argparse

    parser = argparse.ArgumentParser(description="Engine clipsai - prueba directa")
    parser.add_argument("video", help="Ruta al archivo de video")
    parser.add_argument("transcripcion", help="Ruta al archivo de transcripción")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    parser.add_argument("--no-cleanup", action="store_true", help="No limpiar directorio temporal")

    args = parser.parse_args()

    print(f"Procesando: {args.video} + {args.transcripcion}")
    print("-" * 50)

    resultado = procesar_video(args.video, args.transcripcion)

    if args.json:
        print(json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False))
    else:
        if resultado.exito:
            print(f"✓ ÉXITO - {len(resultado.clips)} clips generados")
            print(f"  Carpeta: {resultado.carpeta_salida}")
            for i, clip in enumerate(resultado.clips, 1):
                print(f"  {i}. {os.path.basename(clip.archivo)} | {clip.inicio}-{clip.fin} | Score: {clip.score} | {clip.titulo_sugerido[:50]}")
        else:
            print(f"✗ ERROR [{resultado.error_tipo}]: {resultado.error}")
            if resultado.error_detalle:
                print(f"  Detalle: {resultado.error_detalle}")

    if not args.no_cleanup and resultado.exito:
        limpiar_directorio_trabajo(resultado.carpeta_salida)
        print("  (Directorio temporal limpiado)")


if __name__ == "__main__":
    _main_cli()
ENGINE_PY_EOF
# Embebido: main.py
COPY <<'MAIN_PY_EOF' ./main.py
#!/usr/bin/env python3
"""
Generador automático de clips virales.
Extracción de audio + análisis automático + IA + recorte.
"""

import os
import re
import json
import time
import subprocess
import sys
import shutil

# Forzar la codificación de la consola a UTF-8 en Windows para evitar errores
# al imprimir caracteres especiales (✓, ►, etc.) en PowerShell
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import logging

import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from audio_analyzer import analizar_audio, guardar_json
    AUDIO_ANALYZER_AVAILABLE = True
except ImportError:
    AUDIO_ANALYZER_AVAILABLE = False


def cargar_env(ruta: str = ".env") -> None:
    """Carga variables de entorno desde un archivo .env si existe."""
    if not os.path.exists(ruta):
        return
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            if clave and clave not in os.environ:
                os.environ[clave] = valor


cargar_env()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
ANTHROPIC_FALLBACK_MODEL = os.environ.get("ANTHROPIC_FALLBACK_MODEL", "claude-haiku-5-5")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_WORKSPACE_ID = os.environ.get("ANTHROPIC_WORKSPACE_ID", "")
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_ENDPOINT = os.environ.get("OPENROUTER_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", os.environ.get("OPENAI_MODEL", "anthropic/claude-3.5-sonnet"))
API_ENDPOINT = os.environ.get("API_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")
MODEL = os.environ.get("MODEL", "deepseek-chat")
TIMEOUT = 180
MAX_INTENTOS = 3


def verificar_ffmpeg() -> bool:
    """Verifica si FFmpeg está instalado."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def verificar_dependencias() -> bool:
    """Verifica que las dependencias estén instaladas."""
    if not PYDUB_AVAILABLE:
        print("Error: pydub no está instalado")
        print("Ejecuta: pip install pydub")
        return False
    return True


def extraer_audio(video_path: str, audio_path: str = "audio.mp3") -> str:
    """Extrae el audio de un video usando FFmpeg."""
    print("[1/6] Extrayendo audio del video...")
    
    if os.path.exists(audio_path):
        os.remove(audio_path)
    
    comando = [
        "ffmpeg", "-y", "-i", video_path,
        "-q:a", "0", "-map", "a", audio_path
    ]
    
    try:
        subprocess.run(comando, capture_output=True, check=True)
        print(f"      Audio guardado: {audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error al extraer audio: {e.stderr.decode()}")


def analizar_audio_video(audio_path: str = "audio.mp3", max_eventos: int = 30) -> List[Dict]:
    """Analiza el audio usando el módulo audio_analyzer."""
    print("[2/6] Analizando audio...")
    
    if not AUDIO_ANALYZER_AVAILABLE:
        print("      audio_analyzer no disponible")
        return []
    
    try:
        eventos = analizar_audio(audio_path, "audio.json")
        
        if os.path.exists("momentos_virales.json"):
            with open("momentos_virales.json", "r", encoding="utf-8") as f:
                momentos = json.load(f)
            if momentos and "momentos" in momentos:
                eventos_cluster = momentos["momentos"]
                print(f"      Momentos virales del clustering: {len(eventos_cluster)}")
                
                for mc in eventos_cluster[:5]:
                    eventos.append({
                        "timestamp": mc.get("timestamp", "0:00"),
                        "intensidad": mc.get("intensidad", 7.0),
                        "tipo": "momento_viral",
                        "score_ia": mc.get("score_ia", 8),
                        "criterio": mc.get("criterio_principal", "viral"),
                    })
        
        eventos = sorted(eventos, key=lambda x: x.get("intensidad", 0), reverse=True)
        eventos_top = eventos[:50]
        eventos_top = sorted(eventos_top, key=lambda x: x.get("timestamp", ""))
        
        print(f"      Eventos detectados: {len(eventos)}, usando top {len(eventos_top)}")
        return eventos_top
    except Exception as e:
        print(f"      Error en análisis: {e}")
        return []


def leer_transcripcion_completa(ruta: str) -> str:
    """Lee el archivo completo sin límite. Usar para formatear_transcripcion()."""
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read().strip()


def leer_transcripcion_para_ia(ruta: str, max_chars: int = 6000) -> str:
    """Lee con límite de chars. Usar solo para construir el prompt de la IA."""
    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
    if len(contenido) > max_chars:
        contenido = contenido[:max_chars].rsplit('\n', 1)[0]
        print(f"      Transcripción truncada para IA: {len(contenido)} caracteres")
    return contenido


def leer_transcripcion(ruta: str, max_chars: int = 8000) -> str:
    """Lee el archivo de transcripción (deprecated, usar leer_transcripcion_completa o leer_transcripcion_para_ia)."""
    return leer_transcripcion_completa(ruta)


def formatear_transcripcion(transcripcion_raw: str, salida_path: str = "transcripcion_formatted.txt") -> str:
    """
    Convierte la transcripción cruda de YouTube al formato HH:MM:SS - Texto
    SIN modificar los timestamps ni el texto. Solo limpia y reformatea.
    Procesa TODAS las líneas sin límite.
    """
    import re
    
    print("[3.5/6] Formateando transcripción completa...")
    
    lineas_raw = transcripcion_raw.strip().split('\n')
    segmentos = []
    texto_pendiente = ""
    timestamp_actual = None
    
    RE_TS = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)')
    RE_SEG = re.compile(r'^\d+\s+(segundo|minuto|hora)s?', re.IGNORECASE)
    RE_MIN = re.compile(r'^\d+\s+minutos?\s+y\s+\d+\s+segundos?', re.IGNORECASE)
    
    for linea in lineas_raw:
        linea = linea.strip()
        if not linea:
            continue
        
        match_ts = RE_TS.match(linea)
        if match_ts:
            if texto_pendiente and timestamp_actual:
                h, m, s = _parse_timestamp(timestamp_actual)
                segmentos.append((f"{h:02d}:{m:02d}:{s:02d}", texto_pendiente))
            
            ts_str = match_ts.group(1)
            texto_restante = linea[len(match_ts.group(0)):].strip()
            
            texto_restante = RE_SEG.sub('', texto_restante)
            texto_restante = RE_MIN.sub('', texto_restante)
            
            timestamp_actual = ts_str
            texto_pendiente = texto_restante
        else:
            if texto_pendiente:
                texto_pendiente += " " + linea
    
    if texto_pendiente and timestamp_actual:
        h, m, s = _parse_timestamp(timestamp_actual)
        segmentos.append((f"{h:02d}:{m:02d}:{s:02d}", texto_pendiente))
    
    if not segmentos:
        print("      ✗ No se pudieron parsear segmentos")
        return transcripcion_raw
    
    with open(salida_path, "w", encoding="utf-8") as f:
        for ts, texto in segmentos:
            f.write(f"{ts} - {texto}\n")
    
    ts_primero = segmentos[0][0]
    ts_ultimo = segmentos[-1][0]
    print(f"      ✓ Transcripción formateada: {salida_path} ({len(segmentos)} segmentos)")
    print(f"      Rango: {ts_primero} hasta {ts_ultimo}")
    for i, (ts, txt) in enumerate(segmentos[:5]):
        print(f"        {ts}: {txt[:50]}...")
    
    return salida_path


def _parse_timestamp(ts: str) -> tuple:
    """Convierte timestamp M:SS o H:MM:SS a (h, m, s)."""
    partes = ts.split(':')
    if len(partes) == 2:
        return (0, int(partes[0]), int(partes[1]))
    elif len(partes) == 3:
        return (int(partes[0]), int(partes[1]), int(partes[2]))
    return (0, 0, 0)


def preparar_transcripcion_para_ia(ruta: str = "transcripcion_formatted.txt", max_segmentos: int = 150) -> str:
    """
    Comprime la transcripción para la IA mientras preserva todos los timestamps.
    Mantiene estructura completa pero elimina redundancias.
    """
    print("[3.8/6] Preparando transcripción para IA...")
    
    with open(ruta, "r", encoding="utf-8") as f:
        lineas = [l.strip() for l in f.readlines() if l.strip()]
    
    segmentos = []
    for linea in lineas:
        if " - " in linea:
            partes = linea.split(" - ", 1)
            ts = partes[0].strip()
            texto = partes[1].strip()
            segmentos.append((ts, texto))
    
    if not segmentos:
        return ""
    
    total_segmentos = len(segmentos)
    print(f"      Total segmentos: {total_segmentos}")
    
    if total_segmentos <= max_segmentos:
        resultado = "\n".join([f"{ts} - {texto}" for ts, texto in segmentos])
        print(f"      Sin comprimir (≤{max_segmentos} segmentos)")
        return resultado
    
    factor = total_segmentos / max_segmentos
    paso = int(factor)
    if paso < 1:
        paso = 1
    
    segmentos_comprimidos = []
    for i in range(0, total_segmentos, paso):
        ts, texto = segmentos[i]
        
        if i + paso < total_segmentos:
            textos_combined = [texto]
            for j in range(i + 1, min(i + paso, total_segmentos)):
                textos_combined.append(segmentos[j][1])
            texto = " ".join(textos_combined)
        
        segmentos_comprimidos.append((ts, texto))
    
    resultado = "\n".join([f"{ts} - {texto}" for ts, texto in segmentos_comprimidos])
    print(f"      Comprimida: {len(segmentos_comprimidos)} segmentos (factor {factor:.1f}x)")
    
    return resultado


def enriquecer_datos_para_ia(datos_audio: List[Dict], transcripcion_path: str = "transcripcion_formatted.txt") -> Dict:
    """
    Correlaciona eventos de audio con segmentos de transcripción.
    Returns un diccionario con datos enriquecidos para la IA.
    """
    print("[3.9/6] Enriqueciendo datos para IA...")
    
    with open(transcripcion_path, "r", encoding="utf-8") as f:
        lineas = [l.strip() for l in f.readlines() if l.strip() and " - " in l]
    
    segmentos_ts = []
    for linea in lineas:
        partes = linea.split(" - ", 1)
        ts = partes[0].strip()
        texto = partes[1].strip()
        segmentos_ts.append((ts, texto))
    
    def ts_a_segundos(ts: str) -> float:
        partes = ts.split(":")
        if len(partes) == 3:
            return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
        elif len(partes) == 2:
            return int(partes[0]) * 60 + int(partes[1])
        return 0.0
    
    eventos_enriquecidos = []
    
    for evento in datos_audio:
        ts_evento = evento.get("timestamp", "0:00")
        seg_evento = ts_a_segundos(ts_evento)
        
        mejor_segmento = None
        mejor_distancia = float("inf")
        
        for ts, texto in segmentos_ts:
            seg_ts = ts_a_segundos(ts)
            distancia = abs(seg_evento - seg_ts)
            if distancia < mejor_distancia:
                mejor_distancia = distancia
                mejor_segmento = (ts, texto)
        
        if mejor_segmento and mejor_distancia < 30:
            eventos_enriquecidos.append({
                "timestamp": ts_evento,
                "intensidad": evento.get("intensidad", 5),
                "tipo": evento.get("tipo", "evento"),
                "texto_correlacionado": mejor_segmento[1][:200],
                "timestamp_transcripcion": mejor_segmento[0],
                "distancia_segundos": mejor_distancia,
            })
    
    print(f"      Eventos enriquecidos: {len(eventos_enriquecidos)}")
    
    return {
        "eventos": eventos_enriquecidos,
        "total_segmentos": len(segmentos_ts),
        "correlacion_exitosa": len(eventos_enriquecidos),
    }


def construir_prompt(transcripcion: str, datos_audio: List[Dict], datos_enriquecidos: Dict = None) -> str:
    """Construye el prompt para la IA."""
    
    if datos_enriquecidos and datos_enriquecidos.get("eventos"):
        audio_json = json.dumps(datos_enriquecidos["eventos"], indent=2, ensure_ascii=False)
    else:
        audio_json = json.dumps(datos_audio, indent=2, ensure_ascii=False)
    
    return f"""Sos un experto en crear contenido viral para redes sociales (TikTok, Reels, Shorts). Tu objetivo es encontrar los momentos más interesantes, emocionantes, polémicos, educativos o informativos de CUALQUIER tipo de video. No importa si es deporte, entrevista, vlog, tutorial, gaming, música, noticias o cualquier otro género. Buscá los segmentos que más enganchen a la audiencia.

DEVOLVÉ ÚNICAMENTE UN ARRAY JSON VÁLIDO. Sin texto antes ni después. Sin markdown. Empezá con [ y terminá con ].

REGLA OBLIGATORIA: Debés devolver SIEMPRE un array con entre 1 y 5 clips. Si no hay momentos perfectos, elegí los mejores segmentos disponibles como 'mejor esfuerzo'. NUNCA devuelvas un array vacío [].

CRITERIOS DE VIRALIDAD (ordenados por peso):

REVELACIÓN O EXCLUSIVA (peso 10/10)
Información que el espectador no sabía y genera sorpresa. Datos internos, rumores confirmados, primicias. Frases como "tengo la información", "me dijeron", "la verdad es que".

CONTROVERSIA O CONTRADICCIÓN (peso 9/10)
Momentos donde se contradice la versión oficial. Críticas directas. Predicciones arriesgadas con fundamento. Frases como "no puede ser", "me parece mal", "error garrafal".

DATO CONCRETO IMPACTANTE (peso 8/10)
Números, fechas, montos específicos que sorprenden. Comparaciones que reencuadran la realidad.

MOMENTO EMOCIONAL AUTÉNTICO (peso 7/10)
Nostalgia, pasión, anécdota personal. Momento donde alguien se quiebra o se emociona.

ANÁLISIS TÉCNICO SIMPLE Y CLARO (peso 6/10)
Explicación de por qué pasó algo de manera accesible. Máximo cuando usa metáforas o ejemplos concretos.

PREDICCIÓN O ANTICIPACIÓN (peso 5/10)
Se adelanta algo que va a pasar. Spoiler de una decisión futura. Genera curiosidad sobre si acertó o no.

SEÑALES DE AUDIO QUE AMPLIFICAN EL SCORE:
- intensidad > 7.0 en el timestamp: +1 punto al score
- evento "cambio_brusco" cerca del inicio del clip: +0.5 puntos
- evento "momento_intenso" sostenido: +1 punto
- intensidad < 4.0 (pausa dramática antes del clip): +0.5 puntos

REGLAS PARA DEFINIR INICIO Y FIN DE CADA CLIP:

INICIO del clip:
- OBLIGATORIO: empezar 3-4 segundos ANTES de la frase clave para dar contexto completo
- Nunca cortar en medio de una oración
- Preferir iniciar después de una pausa natural (silencio en datos de audio)
- El primer segundo debe enganchar: pregunta, dato impactante o afirmación fuerte

FIN del clip:
- OBLIGATORIO: terminar 3-4 segundos DESPUÉS de que cierre la idea
- Terminar en punto final de idea (punto, no coma), nunca a mitad de frase
- Ideal: terminar con conclusión, frase de impacto, o transición natural
- Dejar al espectador con ganas de saber más (cliffhanger) cuando sea posible
- OBLIGATORIO: clips de 30-90 segundos (mínimo 30, máximo 90)
- El punto óptimo es 45-70 segundos para TikTok/Reels

EVITAR:
- Clips que empiezan con "y", "pero", "entonces" sin contexto previo
- Clips que cortan la idea a la mitad (debe cerrar la idea completamente)
- Dos clips con el mismo tema o personaje
- Clips de más de 80 segundos salvo que sea una revelación excepcional

DATOS DE AUDIO DEL VIDEO:
{audio_json}

Instrucciones para usar los datos de audio:
- Buscá timestamps con intensidad >= 7.5: son momentos de alta energía vocal
- Los eventos "cambio_brusco" marcan transiciones abruptas de tema
- Los eventos "momento_intenso" indican energía sostenida (bueno para clips)
- Correlacioná los timestamps del audio con los timestamps de la transcripción para validar que los clips propuestos coincidan con momentos de energía alta

TRANSCRIPCIÓN COMPLETA:
{transcripcion}

FORMATO JSON DE SALIDA OBLIGATORIO:
REGLAS OBLIGATORIAS DE DURACIÓN:
- CADA clip debe durar entre 30 y 90 SEGUNDOS
- NO ACCEPTAR clips menores a 30 segundos
- NO ACCEPTAR clips mayores a 90 segundos
- La duración se calcula como: fin - inicio
- Si un clip dura menos de 30s, NO ES VÁLIDO - debes extenderlo
- La IA debe asegurar que cada clip propuesto cumpla 30-90s
[
{{
"inicio": "HH:MM:SS",
"fin": "HH:MM:SS",
"duracion": 35,
"score": 9,
"criterio_principal": "revelacion",
"titulo_sugerido": "La VERDAD de por qué sacaron a Bustos",
"hook_texto": "Lo que nadie te contó",
"primer_segundo": "frase exacta con la que arranca el clip",
"motivo": "explicación de por qué es viral en 1 oración",
"tipo_contenido": "exclusiva",
"audio_score": 8
}}

CAMPOS OBLIGATORIOS:
- inicio/fin: timestamps exactos en HH:MM:SS
- duracion: segundos enteros (fin - inicio)
- score: 1-10 basado en criterios de viralidad
- criterio_principal: uno de [revelacion, controversia, dato_impactante, emocional, analisis_tactico, prediccion]
- titulo_sugerido: título para el clip en español rioplatense, max 60 chars, sin clickbait vacío, con el dato concreto que engancha
- hook_texto: texto del gancho inicial (2-5 palabras), distinto para cada clip
- primer_segundo: primeras palabras exactas de la transcripción que abre el clip
- motivo: por qué este momento específico va a generar engagement
- tipo_contenido: uno de [exclusiva, analisis, emocion, prediccion, controversia]
- audio_score: 1-10 basado en los datos de audio en ese rango de tiempo

REGLAS FINALES:
- Asigná un score del 1 al 10, pero incluí todos los clips que tengan al menos un 5
- Devolvé entre 1 y 5 clips (NUNCA 0)
- No repetir el mismo tema o personaje en más de 2 clips
- El primer clip del array DEBE ser el de mayor score
- Todos los timestamps deben existir en la transcripción proporcionada
- Empezá con [ y terminá con ]"""


def _post_con_retry(url: str, headers: Dict, body: Dict, timeout: int = TIMEOUT, intentos: int = MAX_INTENTOS) -> requests.Response:
    """POST con reintentos automáticos ante cortes de conexión."""
    for intento in range(1, intentos + 1):
        try:
            return requests.post(url, headers=headers, json=body, timeout=timeout)
        except requests.exceptions.Timeout:
            if intento == intentos:
                raise TimeoutError("La solicitud excedió el tiempo de espera")
        except requests.exceptions.RequestException as e:
            if intento == intentos:
                raise ConnectionError(f"Error de conexión: {e}")
        print(f"      Intento {intento} falló, reintentando en {2 * intento}s...")
        time.sleep(2 * intento)


def llamar_claude(prompt: str) -> str:
    """Llama a la API de Anthropic Claude y devuelve el texto de la respuesta."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Define ANTHROPIC_API_KEY en el archivo .env")

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    if ANTHROPIC_WORKSPACE_ID:
        headers["anthropic-workspace-id"] = ANTHROPIC_WORKSPACE_ID
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "thinking": {"type": "between_tools"},
        "messages": [{"role": "user", "content": prompt}],
    }

    respuesta = _post_con_retry(ANTHROPIC_ENDPOINT, headers, body)
    if respuesta.status_code != 200:
        raise ConnectionError(f"Error {respuesta.status_code}: {respuesta.text[:500]}")

    datos = respuesta.json()
    texto = ""
    for bloque in datos.get("content", []):
        if bloque.get("type") == "text" and bloque.get("text"):
            texto += bloque["text"]
    if texto:
        return texto
    raise ValueError("Respuesta inválida de la API: sin bloque de texto")


def llamar_openai_compatible(prompt: str) -> str:
    """Llama a una API estilo OpenAI (DeepSeek/OpenRouter/u otra) y devuelve el texto."""
    key = OPENAI_API_KEY or OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        raise ValueError("Define OPENAI_API_KEY / OPENROUTER_API_KEY / DEEPSEEK_API_KEY en .env")
    if OPENROUTER_API_KEY:
        endpoint = OPENROUTER_ENDPOINT
        model = OPENROUTER_MODEL
        eff_key = OPENROUTER_API_KEY
    elif os.getenv("DEEPSEEK_API_KEY", "") and not OPENAI_API_KEY:
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        model = os.getenv("MODEL", "deepseek-chat")
        eff_key = os.getenv("DEEPSEEK_API_KEY", "")
    else:
        endpoint = API_ENDPOINT
        model = MODEL
        eff_key = OPENAI_API_KEY
    headers = {
        "Authorization": f"Bearer {eff_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://clipsai.local",
        "X-Title": "ClipsAI",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    respuesta = _post_con_retry(endpoint, headers, body)
    if respuesta.status_code != 200:
        raise ConnectionError(f"Error {respuesta.status_code}: {respuesta.text[:500]}")

    try:
        datos = respuesta.json()
        return datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Respuesta inválida de la API: {e}")


def obtener_clips_ia(transcripcion: str, datos_audio: List[Dict], datos_enriquecidos: Dict = None) -> List[Dict]:
    """Envía datos a la IA y retorna los clips detectados. Fallback robusto con logger."""
    has_anthropic = bool(ANTHROPIC_API_KEY)
    has_openai = bool(os.getenv("OPENAI_API_KEY", ""))
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY", ""))
    has_deepseek = bool(os.getenv("DEEPSEEK_API_KEY", ""))

    if not has_anthropic and not has_openai and not has_openrouter and not has_deepseek:
        raise ValueError(
            "Falta la clave de API para la inteligencia artificial. "
            "Por favor completa una de estas variables en tu archivo `.env`: "
            "- ANTHROPIC_API_KEY (para Claude/Anthropic)"
            "- OPENAI_API_KEY (para OpenAI)"
            "- OPENROUTER_API_KEY (para OpenRouter)"
            "- DEEPSEEK_API_KEY (para DeepSeek)"
        )

    if ANTHROPIC_API_KEY:
        proveedor = "Claude (Anthropic)"
    elif OPENROUTER_API_KEY:
        proveedor = "OpenRouter"
    elif OPENAI_API_KEY:
        proveedor = "OpenAI"
    else:
        proveedor = "DeepSeek"
    print(f"[4/6] Analizando con IA ({proveedor})...")

    print(f"[DEBUG CLAUDE] Transcripción enviada ({len(transcripcion)} chars): {transcripcion[:300]}...")
    
    prompt = construir_prompt(transcripcion, datos_audio, datos_enriquecidos)

    try:
        if ANTHROPIC_API_KEY:
            contenido = llamar_claude(prompt)
        else:
            contenido = llamar_openai_compatible(prompt)
    except Exception:
        logger.exception("Fallo llamada LLM proveedor=%s, intentando fallback alternativo", proveedor)
        fallback = None
        if ANTHROPIC_API_KEY:
            try:
                fallback = llamar_claude(prompt) if proveedor != "Claude (Anthropic)" else None
            except Exception:
                logger.exception("Fallback Anthropic también falló")
        if fallback is None and (OPENROUTER_API_KEY or OPENAI_API_KEY or has_deepseek):
            try:
                contenido = llamar_openai_compatible(prompt)
                fallback = contenido
            except Exception:
                logger.exception("Fallback OpenAI/OpenRouter/DeepSeek falló")
        if fallback is not None:
            contenido = fallback
        else:
            raise

    print(f"      Respuesta IA ({len(contenido)} chars)")
    print(f"      === RESPUESTA COMPLETA ===")
    print(contenido[:2000])
    print(f"      === FIN RESPUESTA ===")
    
    # Loggear respuesta cruda completa para debug
    logger.info("Respuesta Claude raw (completa): %s", contenido)
    print(f"[DEBUG CLAUDE] Respuesta cruda recibida ({len(contenido)} chars): {contenido[:500]}...")
    
    # 1. Si viene envuelto en markdown fences ```json ... ```, extraerlo primero
    md_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido)
    if md_match:
        print(f"      Detectado JSON dentro de markdown fences")
        contenido = md_match.group(1).strip()
    
    # 2. Buscar el array JSON más largo posible (puede haber texto antes/después)
    json_match = re.search(r'\[[\s\S]*\]', contenido)
    if not json_match:
        # 3. Fallback: buscar objetos individuales { ... }
        print(f"      No se encontró array JSON. Buscando objetos individuales...")
        print(f"      Preview crudo: {contenido[:500]}...")
        try:
            raw = contenido.strip()
            if raw.startswith("{") and raw.endswith("}"):
                data = json.loads(raw)
                if "clips" in data and isinstance(data["clips"], list):
                    clips = data["clips"]
                    print(f"      Extraidos {len(clips)} clips desde objeto con clave 'clips'")
                    return clips
            # Último intento: parsear objetos sueltos
            objetos = []
            for m in re.finditer(r'\{[^{}]*\}', contenido):
                try:
                    obj = json.loads(m.group())
                    if "inicio" in obj and "fin" in obj:
                        objetos.append(obj)
                except json.JSONDecodeError:
                    continue
            if objetos:
                print(f"      Extraidos {len(objetos)} clips desde objetos sueltos")
                return objetos
        except Exception as ex:
            logger.warning("Fallback parse failed: %s", ex)
        raise ValueError("No se encontró JSON válido en la respuesta de la IA")
    
    json_str = json_match.group(0)
    clips = parsear_json_tolerante(json_str)
    if not clips:
        print(f"      JSON parse devolvió 0 clips. Respuesta raw:")
        print(contenido[:2000])
        raise ValueError("No se pudo parsear la respuesta como JSON")
    
    print(f"      IA detectó {len(clips)} momentos")
    return clips


def timestamp_a_segundos(timestamp: str) -> float:
    """Convierte timestamp a segundos (maneja HH:MM:SS, MM:SS, o segundos)."""
    timestamp = str(timestamp).strip()
    
    try:
        if ':' in timestamp:
            partes = timestamp.split(':')
            if len(partes) == 2:
                return int(partes[0]) * 60 + float(partes[1])
            elif len(partes) == 3:
                return int(partes[0]) * 3600 + int(partes[1]) * 60 + float(partes[2])
        else:
            return float(timestamp)
    except ValueError:
        return 0.0
    
    return 0.0


def reparar_json(texto: str) -> str:
    """Intenta reparar JSON común malformado."""
    texto = texto.strip()
    
    texto = re.sub(r"(\w+)\s*:\s*", r'"\1": ', texto)
    
    texto = re.sub(r":\s*'([^']*)'", r': "\1"', texto)
    
    texto = re.sub(r",(\s*[}\]])", r'\1', texto)
    
    texto = re.sub(r"(\d+)\s+(\d+:)", r'\1,\2', texto)
    
    return texto


def parsear_json_tolerante(texto: str) -> List[Dict]:
    """Intenta parsear JSON, intentando reparar errores comunes."""
    texto = texto.strip()
    
    # Si viene envuelto en markdown fences, limpiar
    md_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', texto)
    if md_match:
        texto = md_match.group(1).strip()
    
    first_bracket = texto.find('[')
    last_bracket = texto.rfind(']')
    
    if first_bracket == -1 or last_bracket == -1:
        json_str = texto
    else:
        json_str = texto[first_bracket:last_bracket+1]
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    try:
        reparado = reparar_json(json_str)
        return json.loads(reparado)
    except json.JSONDecodeError:
        pass
    
    try:
        objetos = []
        for match in re.finditer(r'\{[^{}]*\}', json_str):
            try:
                obj = json.loads(match.group())
                if "inicio" in obj and "fin" in obj:
                    objetos.append(obj)
            except:
                continue
        return objetos
    except:
        return []
    """Convierte segundos a HH:MM:SS."""
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segs = segundos % 60
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


def validar_clips(clips: List[Dict]) -> List[Dict]:
    """Valida y filtra los clips."""
    print("[5/6] Validando clips...")
    
    def convertir_ts(ts):
        partes = ts.split(':')
        if len(partes) == 2:
            return int(partes[0]) * 60 + int(partes[1])
        elif len(partes) == 3:
            return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
        return 0
    
    def formatear_ts(segundos):
        h = segundos // 3600
        m = (segundos % 3600) // 60
        s = segundos % 60
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    
    clips_validos = []
    
    print(f"      DEBUG: {len(clips)} clips recibidos de IA")
    
    for i, clip in enumerate(clips):
        if "inicio" not in clip or "fin" not in clip:
            print(f"      DEBUG clip {i+1}: sin inicio/fin")
            continue
        
        score = clip.get("score", 5)
        
        inicio = str(clip["inicio"])
        fin = str(clip["fin"])
        
        try:
            inicio_seg = convertir_ts(inicio)
            fin_seg = convertir_ts(fin)
        except Exception as e:
            print(f"      DEBUG clip {i+1}: error parseo ts: {e}")
            continue
        
        duracion = fin_seg - inicio_seg
        
        if duracion < 30 or duracion > 90:
            print(f"      DEBUG clip {i+1}: duracion {duracion}s fuera de rango (15-120)")
            continue
        
        if score < 5:
            print(f"      DEBUG clip {i+1}: score {score} < 5 (umbral mínimo)")
            continue
        
        criterio = clip.get("criterio_principal", "otro")
        titulo = clip.get("titulo_sugerido", "")
        
        clips_validos.append({
            "inicio": formatear_ts(inicio_seg),
            "fin": formatear_ts(fin_seg),
            "duracion": duracion,
            "score": score,
            "intensidad": clip.get("intensidad", 5),
            "audio_score": clip.get("audio_score", 5),
            "criterio_principal": criterio,
            "titulo_sugerido": titulo,
            "hook_texto": clip.get("hook_texto", ""),
            "primer_segundo": clip.get("primer_segundo", ""),
            "motivo": clip.get("motivo", ""),
            "tipo_contenido": clip.get("tipo_contenido", "otro"),
        })
        print(f"      Clip {i+1}: {formatear_ts(inicio_seg)} - {formatear_ts(fin_seg)} ({duracion}s) | {criterio} | Score: {score} | {titulo[:40]}")
    
    clips_validos.sort(key=lambda x: x["score"], reverse=True)
    clips_validos = clips_validos[:10]
    
    print(f"      Clips válidos: {len(clips_validos)}")
    return clips_validos


def crear_carpeta_salida(nombre: str = "clips") -> str:
    """Crea la carpeta de salida."""
    if not os.path.exists(nombre):
        os.makedirs(nombre)
    return nombre


def cortar_clip(video_entrada: str, inicio: str, fin: str, salida: str) -> bool:
    """Corta un clip usando FFmpeg."""
    # Debug: mostrar qué FFmpeg estamos usando
    ffmpeg_path = shutil.which("ffmpeg")
    print(f"      [DEBUG] Usando FFmpeg en: {ffmpeg_path}")
    
    # Verificar que el archivo de entrada existe
    if not os.path.exists(video_entrada):
        print(f"      ERROR CRITICO: El archivo de video de entrada NO existe: {video_entrada}")
        return False
    
    inicio_seg = timestamp_a_segundos(inicio)
    fin_seg = timestamp_a_segundos(fin)
    duracion = int(fin_seg - inicio_seg)
    
    if duracion <= 0:
        print(f"      Duración inválida: {duracion}s (inicio={inicio}, fin={fin})")
        return False
    
    print(f"      Corte: {inicio} -> {fin} (duración: {duracion}s)")
    
    try:
        comando = [
            "/usr/local/bin/ffmpeg", "-y",
            "-i", video_entrada,           # Entrada primero
            "-ss", str(inicio),             # Slow seek (después de -i)
            "-t", str(duracion),            # Duración
            "-c:v", "libx264",              # Codec de video estándar
            "-c:a", "aac",                  # Codec de audio estándar
            "-movflags", "+faststart",      # Optimización para web
            salida
        ]
        comando_str = " ".join(comando)
        print(f"      Ejecutando: {comando_str}")
        
        result = subprocess.run(comando, capture_output=True, timeout=120)
        if result.returncode != 0:
            stderr_msg = result.stderr.decode("utf-8", errors="ignore")
            print(f"      Ffmpeg FALLÓ. Return code: {result.returncode}")
            print(f"      Ffmpeg stderr completo:\n{stderr_msg}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"      Timeout al cortar clip")
        return False
    except subprocess.CalledProcessError as e:
        print(f"      Error al cortar: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else e}")
        return False


def procesar_clips(video_entrada: str, clips: List[Dict], carpeta: str) -> List[str]:
    """Genera todos los clips."""
    print("[6/6] Generando clips...")
    
    archivos = []
    info_clips = []
    
    for i, clip in enumerate(clips, 1):
        nombre = os.path.join(carpeta, f"clip_{i}.mp4")
        inicio = str(clip["inicio"])
        fin = str(clip["fin"])
        print(f"      Clip {i}: inicio={inicio}, fin={fin}")
        
        if cortar_clip(video_entrada, inicio, fin, nombre):
            if os.path.exists(nombre):
                tamano = os.path.getsize(nombre)
                print(f"      ✓ Guardado: {nombre} ({tamano} bytes)")
            else:
                print(f"      ✗ Archivo no creado")
            archivos.append(nombre)
            info_clips.append({
                "archivo": nombre,
                "inicio": clip["inicio"],
                "fin": clip["fin"],
                "titulo_sugerido": clip.get("titulo_sugerido", ""),
                "hook_texto": clip.get("hook_texto", ""),
                "criterio_principal": clip.get("criterio_principal", ""),
                "score": clip.get("score", 0),
                "primer_segundo": clip.get("primer_segundo", ""),
                "motivo": clip.get("motivo", ""),
            })
        else:
            print(f"      ✗ Falló")
    
    with open(os.path.join(carpeta, "clips_info.json"), "w", encoding="utf-8") as f:
        json.dump(info_clips, f, indent=2, ensure_ascii=False)
    
    return archivos


def main():
    """Función principal."""
    print("=" * 50)
    print("  CLIP GENERATOR")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("\nUso:")
        print("  Con transcripción manual: python main.py video.mp4 transcripcion.txt")
        print("  Modo automático (Whisper): python main.py video.mp4")
        print("  Solo mejor clip: python main.py video.mp4 --single")
        print("  Corte manual: python main.py video.mp4 00:01:00 00:01:30")
        print("\nEjemplos:")
        print("  python main.py video.mp4 transcripcion.txt")
        print("  python main.py video.mp4  (usa Whisper automático)")
        print("  python main.py video.mp4 --single")
        print("=" * 50)
        sys.exit(1)
    
    video = sys.argv[1]
    
    if not os.path.exists(video):
        print(f"\nError: Video '{video}' no encontrado\n")
        sys.exit(1)
    
    if not verificar_ffmpeg():
        print("\nError: FFmpeg no instalado\n")
        sys.exit(1)
    
    carpeta = crear_carpeta_salida("clips")
    print(f"\nCarpeta: {os.path.abspath(carpeta)}\n")
    
    modo_whisper = False
    transcripcion_path = None
    modo_single = False
    
    if len(sys.argv) >= 4:
        if sys.argv[3] == "--single":
            transcripcion_path = sys.argv[2]
            modo_single = True
        else:
            inicio = sys.argv[2]
            fin = sys.argv[3]
            print(f"MODO MANUAL: {inicio} -> {fin}")
            print("=" * 50)
            
            nombre = os.path.join(carpeta, "clip_single.mp4")
            if cortar_clip(video, inicio, fin, nombre):
                if os.path.exists(nombre):
                    tamano = os.path.getsize(nombre)
                    info_clips = [{"archivo": nombre, "inicio": inicio, "fin": fin}]
                    with open(os.path.join(carpeta, "clips_info.json"), "w", encoding="utf-8") as f:
                        json.dump(info_clips, f, indent=2)
                    print(f"\n✓ Clip guardado: {nombre} ({tamano} bytes)")
                    print(f"  Editar con: python editor_viral.py {nombre} clips_editados")
                else:
                    print("\n✗ Error: archivo no creado")
            else:
                print("\n✗ Error al cortar clip")
            sys.exit(0)
    elif len(sys.argv) >= 3:
        transcripcion_path = sys.argv[2]
        if sys.argv[2] == "--single":
            modo_single = True
            transcripcion_path = None
        elif not os.path.exists(transcripcion_path):
            print(f"\nError: Transcripción '{transcripcion_path}' no encontrada\n")
            sys.exit(1)
    else:
        modo_whisper = True
    
    print("MODO AUTOMÁTICO")
    if modo_single:
        print("  (Solo el mejor clip)")
    if modo_whisper:
        print("  (Transcripción con Whisper)")
    print("=" * 50)
    
    try:
        audio_path = extraer_audio(video)
        
        datos_audio = []
        if AUDIO_ANALYZER_AVAILABLE:
            datos_audio = analizar_audio_video(audio_path)
        else:
            print("      Saltando análisis de audio (audio_analyzer no instalado)")
        
        if transcripcion_path and os.path.exists(transcripcion_path):
            from whisper_transcriber import parsear_transcripcion_youtube
            print("\n[3/6] Parseando transcripción...")
            parsear_transcripcion_youtube(
                transcripcion_path,
                "transcripcion_formatted.txt"
            )
            texto_para_ia = leer_transcripcion_para_ia("transcripcion_formatted.txt")
            print("      Modo: transcripción manual (instantáneo)")
        else:
            from whisper_transcriber import transcribir_video
            print("\n[3/6] Transcribiendo con faster-whisper...")
            print("      Modelo: large-v3-turbo (4x más rápido)")
            transcribir_video(
                video,
                "transcripcion_formatted.txt"
            )
            texto_para_ia = leer_transcripcion_para_ia("transcripcion_formatted.txt")
            print("      Modo: faster-whisper automático")
        
        if texto_para_ia:
            datos_enriquecidos = enriquecer_datos_para_ia(datos_audio, "transcripcion_formatted.txt")
            texto_para_ia = preparar_transcripcion_para_ia("transcripcion_formatted.txt")
            clips_ia = obtener_clips_ia(texto_para_ia, datos_audio, datos_enriquecidos)
        else:
            clips_ia = []
        
        clips_validos = validar_clips(clips_ia)
        
        if not clips_validos:
            print("\nNo se encontraron clips válidos")
            sys.exit(0)
        
        if modo_single:
            print(f"\nProcesando solo el mejor clip (score: {clips_validos[0]['score']})")
            mejor_clip = [clips_validos[0]]
            archivos = procesar_clips(video, mejor_clip, carpeta)
        else:
            archivos = procesar_clips(video, clips_validos, carpeta)
        
        print("\n" + "=" * 50)
        print(f"  CLIPS GENERADOS: {len(archivos)}")
        print(f"  UBICACIÓN: {os.path.abspath(carpeta)}")
        print("=" * 50)
        
    except ValueError as e:
        print(f"\nError de datos: {e}\n")
        sys.exit(1)
    except ConnectionError as e:
        print(f"\nError de conexión: {e}\n")
        sys.exit(1)
    except TimeoutError as e:
        print(f"\nError de tiempo: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
MAIN_PY_EOF
# Embebido: whisper_transcriber.py
COPY <<'WHISPER_TRANSCRIBER_PY_EOF' ./whisper_transcriber.py
#!/usr/bin/env python3
"""
Transcripción de video para detección de clips virales.
Genera transcripcion_formatted.txt para que la IA analice el contenido.

Modos:
  A) Con transcripcion.txt manual → parser determinístico (instantáneo)
  B) Sin transcripción → faster-whisper large-v3-turbo (5-6 min)
"""

import os
import re
import subprocess
import time
from typing import List


def segundos_a_ms(seg: float) -> str:
    m = int(seg // 60)
    s = int(seg % 60)
    return f"{m}:{s:02d}"


def segundos_a_hhmmss(seg: float) -> str:
    h = int(seg // 3600)
    m = int((seg % 3600) // 60)
    s = int(seg % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def detectar_device(force_gpu: bool = False) -> tuple:
    """Detecta si hay GPU disponible. En RunPod siempre hay GPU RTX."""
    # Si se fuerza GPU o estamos en RunPod (variable de entorno), intentar CUDA
    use_gpu = force_gpu or os.environ.get("RUNPOD_GPU", "").lower() in ("1", "true", "yes")
    
    if use_gpu:
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                print(f"      GPU detectada: {gpu_name}")
                return ("cuda", "float16")
            else:
                print("      CUDA no disponible en torch, usando CPU")
        except ImportError:
            print("      torch no instalado, intentando detectar GPU manualmente...")
            # Fallback: verificar si hay GPU disponible sin torch
            try:
                import subprocess
                result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], 
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    gpu_name = result.stdout.strip()
                    print(f"      GPU detectada vía nvidia-smi: {gpu_name}")
                    return ("cuda", "float16")
            except Exception:
                pass
            print("      No se detectó GPU, usando CPU")
        except Exception as e:
            print(f"      Error detectando GPU: {e}, usando CPU")
    
    return ("cpu", "int8")


def _extraer_audio(video_path: str) -> str:
    audio_temp = "audio_trans_temp.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_temp
    ], capture_output=True, check=True)
    return audio_temp


def _remover_descripcion(texto: str) -> str:
    """
    Remueve descripción de tiempo al inicio del texto.
    Maneja texto pegado sin espacio.
    """
    patrones_desc = [
        re.compile(r'^\d+\s+minutos?\s+y\s+\d+\s+segundos?', re.IGNORECASE),
        re.compile(r'^\d+\s+minutos?(?!\s+y)', re.IGNORECASE),
        re.compile(r'^\d+\s+segundos?', re.IGNORECASE),
    ]
    for patron in patrones_desc:
        m = patron.match(texto)
        if m:
            resto = texto[len(m.group(0)):]
            return resto.lstrip()
    return texto


def parsear_transcripcion_youtube(
    ruta: str,
    salida: str = "transcripcion_formatted.txt"
) -> str:
    """Parsea transcripción cruda de YouTube al formato HH:MM:SS - Texto."""
    print("[3/6] Parseando transcripción de YouTube...")
    
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read().strip()
    
    lineas = contenido.split('\n')
    segmentos = []
    timestamp_actual = None
    texto_pendiente = ""
    
    RE_TS = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)')
    RE_LIMPIO = re.compile(r'^\d{2}:\d{2}:\d{2}\s*-\s*')
    
    def _ts_a_hhmmss(ts: str) -> str:
        partes = ts.split(':')
        if len(partes) == 2:
            return f"00:{int(partes[0]):02d}:{int(partes[1]):02d}"
        elif len(partes) == 3:
            return f"{int(partes[0]):02d}:{int(partes[1]):02d}:{int(partes[2]):02d}"
        return "00:00:00"
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        if RE_LIMPIO.match(linea):
            if texto_pendiente and timestamp_actual:
                segmentos.append((timestamp_actual, texto_pendiente.strip()))
            timestamp_actual = linea[:8]
            texto_pendiente = RE_LIMPIO.sub('', linea).strip()
            continue
        
        match = RE_TS.match(linea)
        if match:
            if texto_pendiente and timestamp_actual:
                segmentos.append((timestamp_actual, texto_pendiente.strip()))
            
            ts_raw = match.group(1)
            timestamp_actual = _ts_a_hhmmss(ts_raw)
            resto = linea[len(ts_raw):]
            resto = _remover_descripcion(resto.strip())
            texto_pendiente = resto
        else:
            if texto_pendiente:
                texto_pendiente += " " + linea
    
    if texto_pendiente and timestamp_actual:
        segmentos.append((timestamp_actual, texto_pendiente.strip()))
    
    with open(salida, 'w', encoding='utf-8') as f:
        for ts, texto in segmentos:
            if texto:
                f.write(f"{ts} - {texto}\n")
    
    print(f"      ✓ {len(segmentos)} segmentos parseados")
    if segmentos:
        print(f"      Rango: {segmentos[0][0]} → {segmentos[-1][0]}")
        print(f"      Verificación - primeros 3 segmentos:")
        for ts, txt in segmentos[:3]:
            print(f"        {ts}: {txt[:70]}")
    
    if segmentos:
        primer_ts = segmentos[0][0]
        primer_texto = segmentos[0][1]
        if primer_ts != "00:00:00":
            print(f"      AVISO: Primer timestamp es {primer_ts}, esperado 00:00:00")
        if primer_texto and primer_texto[0].isdigit():
            print(f"      AVISO: Primer texto empieza con número: '{primer_texto[:30]}'")
    
    print(f"      Guardado: {salida}")
    
    return salida


def transcribir_audio(
    audio_path: str,
    salida: str = "transcripcion_formatted.txt",
    modelo: str = "large-v3-turbo",
    idioma: str = "es",
) -> str:
    """Transcribe audio WAV con faster-whisper y genera transcripcion_formatted.txt."""
    print(f"[Whisper] Transcribiendo audio: {audio_path}")
    
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper no instalado.\n"
            "Instalar: pip install faster-whisper"
        )
    
    # Forzar GPU en RunPod (siempre tiene GPU RTX)
    device, compute_type = detectar_device(force_gpu=True)
    print(f"      Device: {device} ({compute_type})")
    
    modelo_mapa = {
        "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "large-v3": "large-v3",
        "medium": "medium",
        "small": "small",
    }
    model_name = modelo_mapa.get(modelo, "deepdml/faster-whisper-large-v3-turbo-ct2")
    
    # Modelo local precargado durante el build (si existe, se usa sin descargar)
    whisper_model_cache = os.environ.get("WHISPER_MODEL_PATH", "/app/whisper_model/models--deepdml--faster-whisper-large-v3-turbo-ct2")
    if os.path.isdir(whisper_model_cache):
        print(f"      Usando modelo local: {whisper_model_cache}")
        model_id = whisper_model_cache
    else:
        model_id = model_name
    
    try:
        if not os.path.isdir(whisper_model_cache):
            print(f"[Whisper] Descargando modelo {model_id} (solo la primera vez)...")
        model = WhisperModel(model_id, device=device, compute_type=compute_type, local_files_only=False)
        
        print(f"      Transcribiendo...")
        segments_gen, info = model.transcribe(
            audio_path,
            language=idioma,
            word_timestamps=False,
            vad_filter=True,
            beam_size=5,
            temperature=0.0,
        )
        
        duracion_total = info.duration
        segmentos_texto = []
        ultimo_tiempo = 0.0
        
        print(f"      Duración: {duracion_total:.0f}s")
        print(f"      [{'░' * 40}] 0%", end='', flush=True)
        
        inicio = time.time()
        
        for segment in segments_gen:
            segmentos_texto.append({
                "ts": segundos_a_ms(segment.start),
                "texto": segment.text.strip()
            })
            ultimo_tiempo = segment.end
            
            progreso = min(ultimo_tiempo / duracion_total, 1.0)
            pct = int(progreso * 100)
            llenos = int(progreso * 40)
            barra = '█' * llenos + '░' * (40 - llenos)
            
            transcurrido = time.time() - inicio
            velocidad = ultimo_tiempo / max(transcurrido, 0.1)
            eta = int((duracion_total - ultimo_tiempo) / max(velocidad, 0.1))
            
            print(
                f"\r      [{barra}] {pct}% | {velocidad:.1f}x | {eta}s restantes    ",
                end='', flush=True
            )
        
        print(f"\r      [{'█'*40}] 100% ✓                              ")
        
        with open(salida, 'w', encoding='utf-8') as f:
            for seg in segmentos_texto:
                if seg['texto']:
                    f.write(f"{seg['ts']} - {seg['texto']}\n")
        
        print(f"      ✓ {len(segmentos_texto)} segmentos transcritos")
        print(f"      Guardado: {salida}")
        
        return salida
        
    except Exception as e:
        raise RuntimeError(f"Error transcribiendo con Whisper: {e}")


def transcribir_video(
    video_path: str,
    salida: str = "transcripcion_formatted.txt",
    modelo: str = "large-v3-turbo",
    idioma: str = "es",
) -> str:
    """Transcribe video con faster-whisper y genera transcripcion_formatted.txt."""
    print("[3/6] Transcribiendo con faster-whisper...")
    print(f"      Modelo: {modelo}")
    print(f"      Estimación: ~5-6 min para video de 11min en CPU")
    
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper no instalado.\n"
            "Instalar: pip install faster-whisper"
        )
    
    # Forzar GPU en RunPod (siempre tiene GPU RTX)
    device, compute_type = detectar_device(force_gpu=True)
    print(f"      Device: {device} ({compute_type})")
    
    modelo_mapa = {
        "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "large-v3": "large-v3",
        "medium": "medium",
        "small": "small",
    }
    model_name = modelo_mapa.get(modelo, "deepdml/faster-whisper-large-v3-turbo-ct2")
    
    # Modelo local precargado durante el build (si existe, se usa sin descargar)
    whisper_model_cache = os.environ.get("WHISPER_MODEL_PATH", "/app/whisper_model/models--deepdml--faster-whisper-large-v3-turbo-ct2")
    if os.path.isdir(whisper_model_cache):
        print(f"      Usando modelo local: {whisper_model_cache}")
        model_id = whisper_model_cache
    else:
        model_id = model_name
    
    audio_temp = _extraer_audio(video_path)
    
    try:
        if not os.path.isdir(whisper_model_cache):
            print(f"[Whisper] Descargando modelo {model_id} (solo la primera vez)...")
        model = WhisperModel(model_id, device=device, compute_type=compute_type, local_files_only=False)
        
        print(f"      Transcribiendo...")
        segments_gen, info = model.transcribe(
            audio_temp,
            language=idioma,
            word_timestamps=False,
            vad_filter=True,
            beam_size=5,
            temperature=0.0,
        )
        
        duracion_total = info.duration
        segmentos_texto = []
        ultimo_tiempo = 0.0
        
        print(f"      Duración: {duracion_total:.0f}s")
        print(f"      [{'░' * 40}] 0%", end='', flush=True)
        
        inicio = time.time()
        
        for segment in segments_gen:
            segmentos_texto.append({
                "ts": segundos_a_ms(segment.start),
                "texto": segment.text.strip()
            })
            ultimo_tiempo = segment.end
            
            progreso = min(ultimo_tiempo / duracion_total, 1.0)
            pct = int(progreso * 100)
            llenos = int(progreso * 40)
            barra = '█' * llenos + '░' * (40 - llenos)
            
            transcurrido = time.time() - inicio
            velocidad = ultimo_tiempo / max(transcurrido, 0.1)
            eta = int((duracion_total - ultimo_tiempo) / max(velocidad, 0.1))
            
            print(
                f"\r      [{barra}] {pct}% | {velocidad:.1f}x | {eta}s restantes    ",
                end='', flush=True
            )
        
        print(f"\r      [{'█'*40}] 100% ✓                              ")
        
        with open(salida, 'w', encoding='utf-8') as f:
            for seg in segmentos_texto:
                if seg['texto']:
                    f.write(f"{seg['ts']} - {seg['texto']}\n")
        
        print(f"      ✓ {len(segmentos_texto)} segmentos transcritos")
        print(f"      Guardado: {salida}")
        
        return salida
        
    finally:
        try:
            os.remove(audio_temp)
        except:
            pass


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso:")
        print("  Con transcripción: python whisper_transcriber.py transcripcion.txt")
        print("  Con video:         python whisper_transcriber.py video.mp4")
        sys.exit(1)
    
    entrada = sys.argv[1]
    salida = sys.argv[2] if len(sys.argv) > 2 else "transcripcion_formatted.txt"
    
    if entrada.endswith('.txt'):
        parsear_transcripcion_youtube(entrada, salida)
    else:
        transcribir_video(entrada, salida)
WHISPER_TRANSCRIBER_PY_EOF
# Embebido: audio_analyzer.py
COPY <<'AUDIO_ANALYZER_PY_EOF' ./audio_analyzer.py
#!/usr/bin/env python3
"""
Módulo de análisis de audio para detección de eventos virales.
Usa librosa para análisis de audio sin IA.
"""

import os
import json
import librosa
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class EventoAudio:
    """Representa un evento detectado en el audio."""
    timestamp: str
    evento: str
    intensidad: float


def cargar_audio(ruta: str) -> Tuple[np.ndarray, int]:
    """Carga un archivo de audio y retorna la señal y sample rate."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")
    
    print(f"  Cargando audio: {ruta}")
    y, sr = librosa.load(ruta, sr=None)
    duracion = len(y) / sr
    print(f"  Duración: {duracion:.1f}s | Sample rate: {sr}Hz")
    return y, sr


def calcular_rms(y: np.ndarray, sr: int, frame_length: int = 2048, hop_length: int = 512) -> Tuple[np.ndarray, np.ndarray]:
    """Calcula RMS (Root Mean Square) del audio."""
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    tiempos = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    return rms, tiempos


def detectar_eventos(rms: np.ndarray, tiempos: np.ndarray) -> List[EventoAudio]:
    """Detecta eventos en el audio basándose en RMS."""
    eventos = []
    
    media_rms = np.mean(rms)
    std_rms = np.std(rms)
    
    umbral_grito = media_rms + 2 * std_rms
    umbral_silencio = media_rms * 0.3
    umbral_cambio = std_rms
    
    print(f"  RMS media: {media_rms:.4f} | std: {std_rms:.4f}")
    
    i = 0
    while i < len(rms):
        frame_rms = rms[i]
        tiempo = tiempos[i]
        
        if frame_rms > umbral_grito:
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(tiempo),
                evento="grito",
                intensidad=float(frame_rms)
            ))
        
        elif frame_rms < umbral_silencio:
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(tiempo),
                evento="silencio",
                intensidad=float(1 - frame_rms / umbral_silencio) * 10
            ))
        
        if i > 0:
            cambio = abs(rms[i] - rms[i-1])
            if cambio > umbral_cambio and frame_rms > media_rms:
                eventos.append(EventoAudio(
                    timestamp=segundos_a_timestamp(tiempo),
                    evento="cambio_brusco",
                    intensidad=float(min(cambio / std_rms, 10))
                ))
        
        i += 1
    
    return eventos


def detectar_momentos_intensos(rms: np.ndarray, tiempos: np.ndarray, umbral: float = None) -> List[EventoAudio]:
    """Detecta momentos con energía alta sostenida."""
    eventos = []
    
    media_rms = np.mean(rms)
    std_rms = np.std(rms)
    
    if umbral is None:
        umbral = media_rms + 1.5 * std_rms
    
    ventana = 5
    i = 0
    while i <= len(rms) - ventana:
        chunk = rms[i:i + ventana]
        if np.mean(chunk) > umbral:
            tiempo_inicio = tiempos[i]
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(tiempo_inicio),
                evento="momento_intenso",
                intensidad=float(np.mean(chunk))
            ))
            i += ventana
        else:
            i += 1
    
    return eventos


def detectar_cambios_escena(y: np.ndarray, sr: int) -> List[EventoAudio]:
    """
    Detecta cambios abruptos de tema/escena usando spectral flux.
    Útil para encontrar puntos de corte naturales entre temas del video.
    """
    eventos = []
    
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            units='time',
            delta=0.5,
            wait=2
        )
        
        for t in onsets:
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(t),
                evento="cambio_escena",
                intensidad=5.0
            ))
    except Exception as e:
        print(f"  AVISO: Error detectando cambios de escena: {e}")
    
    return eventos


def limpiar_eventos(eventos: List[EventoAudio], separacion_min: int = 2) -> List[EventoAudio]:
    """Elimina eventos duplicados muy cercanos."""
    if not eventos:
        return []
    
    eventos_ordenados = sorted(eventos, key=lambda x: x.timestamp)
    eventos_limpios = [eventos_ordenados[0]]
    
    for actual in eventos_ordenados[1:]:
        ultimo = eventos_limpios[-1]
        diff = timestamp_diff(ultimo.timestamp, actual.timestamp)
        
        if diff >= separacion_min:
            eventos_limpios.append(actual)
        elif actual.intensidad > ultimo.intensidad:
            eventos_limpios[-1] = actual
    
    return eventos_limpios


def timestamp_diff(ts1: str, ts2: str) -> float:
    """Calcula diferencia en segundos entre dos timestamps."""
    s1 = timestamp_a_segundos(ts1)
    s2 = timestamp_a_segundos(ts2)
    return abs(s2 - s1)


def timestamp_a_segundos(timestamp: str) -> float:
    """Convierte HH:MM:SS a segundos."""
    partes = timestamp.split(':')
    while len(partes) < 3:
        partes.insert(0, '0')
    return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])


def segundos_a_timestamp(segundos: float) -> str:
    """Convierte segundos a HH:MM:SS."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


def normalizar_intensidad(eventos: List[EventoAudio]) -> List[EventoAudio]:
    """Normaliza intensidad a escala 0-10."""
    if not eventos:
        return eventos
    
    max_intensidad = max(e.intensidad for e in eventos)
    
    if max_intensidad > 0:
        for evento in eventos:
            intensidad_normalizada = (evento.intensidad / max_intensidad) * 10
            intensidad_normalizada = max(3.0, min(10.0, intensidad_normalizada))
            evento.intensidad = round(intensidad_normalizada, 1)
    
    return eventos


def filtrar_eventos(eventos: List[EventoAudio], intensidad_min: float = 3.0) -> List[EventoAudio]:
    """Elimina eventos con intensidad muy baja."""
    return [e for e in eventos if e.intensidad >= intensidad_min]


def eventos_a_dict(eventos: List[EventoAudio]) -> List[Dict]:
    """Convierte eventos a formato diccionario."""
    return [
        {
            "timestamp": e.timestamp,
            "evento": e.evento,
            "intensidad": e.intensidad
        }
        for e in eventos
    ]


def guardar_json(eventos: List[Dict], ruta: str = "audio.json") -> None:
    """Guarda los eventos en un archivo JSON."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(eventos, f, indent=2, ensure_ascii=False)
    print(f"  Guardado: {ruta}")


def detectar_momentos_virales_clustering(
    eventos: List[Dict], 
    n_clusters: int = 10
) -> List[Dict]:
    """
    Usa KMeans clustering para identificar los momentos más representativos
    y diversos del video, evitando clusters de momentos similares repetidos.
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        
        features = []
        eventos_idx = []
        
        for i, evento in enumerate(eventos):
            ts = timestamp_a_segundos(evento.get('timestamp', '00:00:00'))
            intensidad = evento.get('intensidad', 5.0)
            
            tipo_score = {
                'grito': 4,
                'momento_intenso': 3,
                'cambio_brusco': 2,
                'cambio_escena': 1,
                'silencio': 0
            }.get(evento.get('evento', 'silencio'), 0)
            
            features.append([ts, intensidad, tipo_score])
            eventos_idx.append(i)
        
        if len(features) < n_clusters:
            return sorted(eventos, key=lambda x: x.get('intensidad', 0), reverse=True)
        
        X = np.array(features)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        n_clusters_real = min(n_clusters, len(features))
        kmeans = KMeans(n_clusters=n_clusters_real, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        mejores_por_cluster = []
        for cluster_id in range(n_clusters_real):
            indices_cluster = [i for i, l in enumerate(labels) if l == cluster_id]
            if not indices_cluster:
                continue
            mejor_idx = max(indices_cluster, key=lambda i: eventos[i].get('intensidad', 0))
            mejores_por_cluster.append(eventos[mejor_idx])
        
        mejores_por_cluster.sort(key=lambda x: timestamp_a_segundos(x.get('timestamp', '00:00:00')))
        
        print(f"  Clustering: {n_clusters_real} clusters generados")
        return mejores_por_cluster
        
    except Exception as e:
        print(f"  Clustering falló: {e}")
        return sorted(eventos, key=lambda x: x.get('intensidad', 0), reverse=True)


def analizar_audio(audio_path: str = "audio.mp3", salida_path: str = "audio.json") -> List[Dict]:
    """
    Función principal: analiza un archivo de audio y genera audio.json.
    
    Args:
        audio_path: Ruta al archivo de audio (MP3)
        salida_path: Ruta donde guardar el JSON de salida
    
    Returns:
        Lista de diccionarios con los eventos detectados
    """
    print("=" * 40)
    print("  ANALIZADOR DE AUDIO")
    print("=" * 40)
    print("Analizando audio...\n")
    
    try:
        y, sr = cargar_audio(audio_path)
        rms, tiempos = calcular_rms(y, sr)
        
        print("\nDetectando eventos...")
        eventos = detectar_eventos(rms, tiempos)
        print(f"  Eventos detectados (gritos/silencios/cambios): {len(eventos)}")
        
        momentos_intensos = detectar_momentos_intensos(rms, tiempos)
        print(f"  Momentos intensos detectados: {len(momentos_intensos)}")
        
        cambios_escena = detectar_cambios_escena(y, sr)
        print(f"  Cambios de escena detectados: {len(cambios_escena)}")
        
        eventos.extend(momentos_intensos)
        eventos.extend(cambios_escena)
        
        print("\nLimpiando eventos...")
        eventos = limpiar_eventos(eventos, separacion_min=2)
        print(f"  Eventos después de limpieza: {len(eventos)}")
        
        print("\nNormalizando intensidad...")
        eventos = normalizar_intensidad(eventos)
        
        eventos = filtrar_eventos(eventos, intensidad_min=3.0)
        print(f"  Eventos después de filtrado: {len(eventos)}")
        
        if not eventos:
            print("\nNo se detectaron eventos relevantes")
            return []
        
        eventos_dict = eventos_a_dict(eventos)
        guardar_json(eventos_dict, salida_path)
        
        print("\nAgrupando momentos con clustering...")
        try:
            momentos_virales = detectar_momentos_virales_clustering(eventos_dict, n_clusters=10)
            guardar_json(momentos_virales, "momentos_virales.json")
            print(f"  Momentos virales seleccionados: {len(momentos_virales)}")
        except Exception as e:
            print(f"  Clustering falló: {e}")
        
        print(f"\n✓ Análisis completado")
        print(f"  Total eventos: {len(eventos_dict)}")
        print("=" * 40)
        
        return eventos_dict
        
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        return []
    except Exception as e:
        print(f"\nError inesperado: {e}")
        return []


def main():
    """Ejemplo de uso."""
    import sys
    
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "audio.mp3"
    salida_path = sys.argv[2] if len(sys.argv) > 2 else "audio.json"
    
    analizar_audio(audio_path, salida_path)


if __name__ == "__main__":
    main()
AUDIO_ANALYZER_PY_EOF
# Embebido: backend_fastapi/runpod_worker.py
COPY <<'RUNPOD_WORKER_PY_EOF' ./runpod_worker.py
import runpod
from backend.handler import handler

runpod.serverless.start({"handler": handler})
RUNPOD_WORKER_PY_EOF

# Sitecustomize embebido inline: reordena PATH para priorizar FFmpeg del sistema
# (con libx264 en /usr/local/bin) sobre /opt/conda/bin. Python lo importa auto.
COPY <<'PYEOF' /usr/local/lib/python3.11/site-packages/sitecustomize.py
import os

_PRIORITY = [
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
]


def _fix_path() -> None:
    current = os.environ.get("PATH", "")
    partes = [p for p in current.split(os.pathsep) if p and p not in _PRIORITY]
    os.environ["PATH"] = os.pathsep.join(_PRIORITY + partes)


_fix_path()
PYEOF

# Crear directorios y permisos
RUN mkdir -p /app/storage/clips /app/storage/uploads \
    && chmod -R 777 /app/storage

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod -R 775 /app/storage

USER appuser

RUN mkdir -p /tmp/huggingface_cache && chown -R appuser:appuser /tmp/huggingface_cache && chmod -R a+rwX /tmp/huggingface_cache

EXPOSE 8000

CMD ["sh", "-c", "echo '[BOOT] RUN_MODE='\"$RUN_MODE\"''; if [ \"$RUN_MODE\" = \"serverless\" ]; then echo '[BOOT] MODO=SERVERLESS (runpod handler)'; exec python runpod_worker.py; else echo '[BOOT] MODO=WEB (uvicorn)'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
