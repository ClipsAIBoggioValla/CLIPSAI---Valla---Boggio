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

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el resultado a diccionario para serialización JSON."""
        return {
            "exito": self.exito,
            "clips": [asdict(c) for c in self.clips],
            "carpeta_salida": self.carpeta_salida,
            "error": self.error,
            "error_tipo": self.error_tipo,
            "error_detalle": self.error_detalle,
        }

    @classmethod
    def exito_resultado(cls, clips: List[ClipInfo], carpeta_salida: str) -> "ProcesamientoResultado":
        """Factory para resultado exitoso."""
        return cls(exito=True, clips=clips, carpeta_salida=carpeta_salida)

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
        from whisper_transcriber import parsear_transcripcion_youtube

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

        # 4.3 Parsear y formatear transcripción
        transcripcion_formatted = os.path.join(trabajo_dir, "transcripcion_formatted.txt")
        try:
            parsear_transcripcion_youtube(transcripcion_original, transcripcion_formatted)
        except Exception as e:
            return ProcesamientoResultado.error_resultado(
                error=f"Falló parseo de transcripción: {e}",
                error_tipo="TranscripcionError",
                error_detalle=traceback.format_exc()
            )

        # 4.4 Preparar datos para IA
        try:
            texto_para_ia = leer_transcripcion_para_ia(transcripcion_formatted)
            datos_enriquecidos = enriquecer_datos_para_ia(datos_audio, transcripcion_formatted)
            texto_para_ia = preparar_transcripcion_para_ia(transcripcion_formatted)
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
            return ProcesamientoResultado.error_resultado(
                error="No se encontraron clips válidos tras análisis de IA",
                error_tipo="SinClipsValidos",
                error_detalle=f"IA devolvió {len(clips_ia)} clips, ninguno pasó validación (duración 30-90s, score>=5)"
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
            return ProcesamientoResultado.error_resultado(
                error="No se pudo generar ningún archivo de clip",
                error_tipo="GeneracionError",
                error_detalle="procesar_clips devolvió lista vacía"
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
            carpeta_salida=clips_dir
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