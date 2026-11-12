#!/usr/bin/env python3
"""
Editor de clips para contenido viral.
Convierte clips horizontales a formato vertical 1080x1920 (9:16) para TikTok/Shorts/Reels.
Solo usa FFmpeg (sin OpenCV).

Cada unidad cambia por un unico motivo (Single Responsibility):

  - `calcular_filtro_vertical()` -> geometria del recorte: logica pura, sin efectos.
  - `verificar_ffmpeg()` / `sondear_dimensiones()` -> utilidades de modulo sin estado.
  - `RenderizadorVertical`       -> dependencias (dimensiones de salida/fps) y ejecucion de ffmpeg.
  - `CatalogoClips`              -> archivos del proyecto (donde estan, donde escribir, metadatos).
  - `VideoEditor`                -> fachada CLI: orquesta catalogo + renderizador por clip.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

ANCHO_FINAL = 1080
ALTO_FINAL = 1920
FPS = 30
INFO_ARCHIVO = "clips_info.json"

# Solo configura la raiz si nadie la configuro antes: asi el CLI muestra los pasos
# numerados y, cuando el modulo se importa dentro de un servidor, respeta el
# logging ya instalado (misma convencion que backend_fastapi/app/routers/jobs.py).
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)


class ClipMetadata(NamedTuple):
    """Etiquetas de un clip leidas de `clips_info.json` (pueden venir vacias)."""

    titulo: str = ""
    criterio: str = ""


def calcular_filtro_vertical(
    ancho: int,
    alto: int,
    ancho_final: int = ANCHO_FINAL,
    alto_final: int = ALTO_FINAL,
) -> str:
    """Devuelve el filtro `crop,scale` que recorta el centro del frame a 9:16.

    Es logica pura: no toca el disco ni lanza procesos, por lo que se puede
    probar de forma aislada.

    Args:
        ancho: ancho del video original en pixels.
        alto: alto del video original en pixels.
        ancho_final: ancho del resultado (por defecto 1080).
        alto_final: alto del resultado (por defecto 1920).

    Returns:
        Cadena de filtro FFmpeg, p.ej. `crop=607:1080:656:0,scale=1080:1920`.

    Raises:
        ValueError: si las dimensiones originales no son validas.
    """
    if ancho <= 0 or alto <= 0:
        raise ValueError(f"Dimensiones de video invalidas: {ancho}x{alto}")

    proporcion = ancho_final / alto_final  # 1080/1920 == 9/16
    ancho_crop = int(alto * proporcion)

    if ancho_crop > ancho:
        # El video ya es mas angosto que el crop: usamos todo el ancho
        # y ajustamos el alto para mantener la proporcion 9:16.
        alto_crop = int(ancho / proporcion)
        crop_y = (alto - alto_crop) // 2
        crop = f"crop={ancho}:{alto_crop}:0:{crop_y}"
    else:
        crop_x = (ancho - ancho_crop) // 2
        crop = f"crop={ancho_crop}:{alto}:{crop_x}:0"

    return f"{crop},scale={ancho_final}:{alto_final}"


def verificar_ffmpeg() -> None:
    """Comprueba que el binario ffmpeg este disponible; relanza el error si no lo esta."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        log.info("  FFmpeg: OK")
    except (FileNotFoundError, subprocess.CalledProcessError):
        log.error("  FFmpeg no encontrado. Instalalo: apt install ffmpeg / brew install ffmpeg")
        raise


def sondear_dimensiones(video_path: str) -> Tuple[int, int]:
    """Obtiene (ancho, alto) del primer stream de video via ffprobe."""
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    ancho, alto = probe.stdout.strip().split("x")
    return int(ancho), int(alto)


class RenderizadorVertical:
    """Unica responsabilidad: ejecutar el render ffmpeg con su configuracion (salida/fps)."""

    def __init__(
        self,
        ancho_final: int = ANCHO_FINAL,
        alto_final: int = ALTO_FINAL,
        fps: int = FPS,
    ):
        self.ancho_final = ancho_final
        self.alto_final = alto_final
        self.fps = fps

    def render(self, video_path: str, salida: str) -> bool:
        """Renderiza `video_path` en 9:16 dentro de `salida`. True si tuvo exito."""
        try:
            ancho, alto = sondear_dimensiones(video_path)
            log.info(f"      Video original: {ancho}x{alto}")

            filtro = calcular_filtro_vertical(ancho, alto, self.ancho_final, self.alto_final)
            log.info(f"      Filtro: {filtro}")

            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vf", filtro,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k",
                    "-r", str(self.fps),
                    "-movflags", "+faststart",
                    salida,
                ],
                capture_output=True, check=True,
            )

            size = Path(salida).stat().st_size
            log.info(f"      Video vertical creado: {size // 1024} KB")
            return True

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or str(e))
            log.error(f"      Error FFmpeg: {stderr[:500]}")
            return False
        except Exception as e:
            log.error(f"      Error: {e}")
            return False


class CatalogoClips:
    """Unica responsabilidad: el sistema de archivos del trabajo (clips y metadatos)."""

    def __init__(self, clips_dir: str, salida_dir: str):
        self.clips_dir = Path(clips_dir)
        self.salida_dir = Path(salida_dir)
        self.salida_dir.mkdir(parents=True, exist_ok=True)

    def listar(self) -> List[Path]:
        return sorted(self.clips_dir.glob("*.mp4"))

    def ruta_salida(self, nombre: str) -> Path:
        return self.salida_dir / f"{nombre}_vertical.mp4"

    def metadatos(self, index: int) -> ClipMetadata:
        """Lee titulo/criterio del indice en `clips_info.json`; tolerantemente vacio."""
        info_path = self.clips_dir / INFO_ARCHIVO
        if not info_path.exists():
            return ClipMetadata()
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                info_clips = json.load(f)
            if index >= len(info_clips):
                return ClipMetadata()
            info = info_clips[index]
            return ClipMetadata(
                titulo=info.get('titulo_sugerido', ''),
                criterio=info.get('criterio_principal', ''),
            )
        except Exception:
            return ClipMetadata()


class VideoEditor:
    """Fachada del editor: orquesta catalogo + renderizador por clip.

    Uso:
        editor = VideoEditor("clips", "clips_editados")
        editor.procesar_todos()          # toda la carpeta
        editor.procesar_clip(clip, 0)    # un clip puntual
    """

    def __init__(self, clips_dir: str = "clips", salida_dir: str = "clips_editados"):
        self.catalogo = CatalogoClips(clips_dir, salida_dir)
        self.renderizador = RenderizadorVertical()
        verificar_ffmpeg()

    def cargar_clips(self) -> List[Path]:
        log.info("[1/2] Cargando clips...")
        clips = self.catalogo.listar()
        log.info(f"      Clips encontrados: {len(clips)}")
        return clips

    def procesar_clip(self, clip_path: Path, index: int) -> Optional[str]:
        """Procesa un clip individual: crop vertical 9:16."""
        log.info(f"\n{'='*40}")
        log.info(f"  PROCESANDO CLIP {index + 1}")
        log.info(f"{'='*40}")

        nombre = clip_path.stem
        salida_final = self.catalogo.ruta_salida(nombre)

        # Leer metadata si existe
        metadatos = self.catalogo.metadatos(index)
        if metadatos.titulo:
            log.info(f"      Titulo: {metadatos.titulo}")
        if metadatos.criterio:
            log.info(f"      Tipo: {metadatos.criterio}")

        if self.renderizador.render(str(clip_path), str(salida_final)):
            log.info(f"      ✓ {os.path.basename(salida_final)}")
            return str(salida_final)
        else:
            log.error(f"      ✗ Falló")
            return None

    def procesar_todos(self) -> List[str]:
        log.info("\n" + "=" * 50)
        log.info("  EDITOR DE VIDEOS VIRALES (FFmpeg)")
        log.info("=" * 50)

        clips = self.cargar_clips()
        if not clips:
            log.warning("No se encontraron clips en " + str(self.catalogo.clips_dir))
            return []

        resultados = []
        for i, clip in enumerate(clips):
            resultado = self.procesar_clip(clip, i)
            if resultado:
                resultados.append(resultado)

        log.info("\n" + "=" * 50)
        log.info(f"  COMPLETADO: {len(resultados)}/{len(clips)} clips")
        log.info(f"  Salida: {self.catalogo.salida_dir}")
        log.info("=" * 50)

        return resultados


def main():
    # Las consolas de Windows con codepage legible (cp1252) revientan al imprimir
    # "✓"/"✗" (UnicodeEncodeError) justo despues de un render exitoso, devolviendo
    # exit 1 a los scripts que invocan el CLI. Se fuerza UTF-8 sin cambiar el texto.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # streams sin reconfigure (p.ej. capturados)
            pass

    if len(sys.argv) < 2:
        print("\nEDITOR DE VIDEOS VIRALES")
        print("=" * 50)
        print("Uso:")
        print("  Todos los clips: python editor_viral.py [carpeta_clips] [carpeta_salida]")
        print("  Un clip:         python editor_viral.py clips/clip_1.mp4 [carpeta_salida]")
        print("\nEjemplos:")
        print("  python editor_viral.py clips clips_editados")
        print("  python editor_viral.py clips/clip_1.mp4 clips_editados")
        print("=" * 50)
        sys.exit(1)

    clips_input = sys.argv[1]
    salida_dir = sys.argv[2] if len(sys.argv) > 2 else "clips_editados"

    input_path = Path(clips_input)
    if input_path.is_file():
        print(f"\nProcesando clip individual: {clips_input}")
        editor = VideoEditor(str(input_path.parent), salida_dir)
        resultado = editor.procesar_clip(input_path, 0)
        if resultado:
            print(f"\n✓ Clip procesado: {resultado}")
        else:
            print("\n✗ Error al procesar clip")
    else:
        editor = VideoEditor(clips_input, salida_dir)
        resultados = editor.procesar_todos()
        for r in resultados:
            print(f"  - {r}")


if __name__ == "__main__":
    main()
