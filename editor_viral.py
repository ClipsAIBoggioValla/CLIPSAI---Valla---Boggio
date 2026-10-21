#!/usr/bin/env python3
"""
Editor de clips para contenido viral.
Convierte clips horizontales a formato vertical 1080x1920 (9:16) para TikTok/Shorts/Reels.
Solo usa FFmpeg (sin OpenCV).
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)


class VideoEditor:
    """Editor de videos virales — crop centrado con FFmpeg."""

    def __init__(self, clips_dir: str = "clips", salida_dir: str = "clips_editados"):
        self.clips_dir = Path(clips_dir)
        self.salida_dir = Path(salida_dir)
        self.salida_dir.mkdir(parents=True, exist_ok=True)

        self.ancho_final = 1080
        self.alto_final = 1920
        self.fps = 30

        self._verificar_ffmpeg()

    def _verificar_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            log.info("  FFmpeg: OK")
        except (FileNotFoundError, subprocess.CalledProcessError):
            log.error("  FFmpeg no encontrado. Instalalo: apt install ffmpeg / brew install ffmpeg")
            raise

    def cargar_clips(self) -> List[Path]:
        log.info("[1/2] Cargando clips...")
        clips = sorted(self.clips_dir.glob("*.mp4"))
        log.info(f"      Clips encontrados: {len(clips)}")
        return clips

    def aplicar_formato_vertical(self, video_path: str, salida: str) -> bool:
        """Crop centrado 9:16 con FFmpeg. Sin OpenCV."""
        log.info("[2/2] Aplicando formato vertical 1080x1920...")

        try:
            # Obtener dimensiones del video original
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
            ancho, alto = int(ancho), int(alto)
            log.info(f"      Video original: {ancho}x{alto}")

            # Calcular crop: tomamos una franja 9:16 centrada
            ratio_objetivo = 9 / 16
            ancho_crop = int(alto * ratio_objetivo)

            # Si el video ya es mas angosto que el crop, usamos todo el ancho
            if ancho_crop > ancho:
                ancho_crop = ancho
                # Ajustamos alto para mantener 9:16
                alto_crop = int(ancho / ratio_objetivo)
                crop_x = 0
                crop_y = (alto - alto_crop) // 2
                filtro = f"crop={ancho_crop}:{alto_crop}:{crop_x}:{crop_y},scale={self.ancho_final}:{self.alto_final}"
            else:
                crop_x = (ancho - ancho_crop) // 2
                filtro = f"crop={ancho_crop}:{alto}:{crop_x}:0,scale={self.ancho_final}:{self.alto_final}"

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
            stderr = e.stderr.decode() if e.stderr else str(e)
            log.error(f"      Error FFmpeg: {stderr[:500]}")
            return False
        except Exception as e:
            log.error(f"      Error: {e}")
            return False

    def procesar_clip(self, clip_path: Path, index: int) -> Optional[str]:
        """Procesa un clip individual: crop vertical 9:16."""
        log.info(f"\n{'='*40}")
        log.info(f"  PROCESANDO CLIP {index + 1}")
        log.info(f"{'='*40}")

        nombre = clip_path.stem
        salida_final = self.salida_dir / f"{nombre}_vertical.mp4"

        # Leer metadata si existe
        info_path = self.clips_dir / "clips_info.json"
        titulo = ""
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info_clips = json.load(f)
                if index < len(info_clips):
                    info = info_clips[index]
                    titulo = info.get('titulo_sugerido', '')
                    criterio = info.get('criterio_principal', '')
                    if titulo:
                        log.info(f"      Titulo: {titulo}")
                    if criterio:
                        log.info(f"      Tipo: {criterio}")
            except Exception:
                pass

        if self.aplicar_formato_vertical(str(clip_path), str(salida_final)):
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
            log.warning("No se encontraron clips en " + str(self.clips_dir))
            return []

        resultados = []
        for i, clip in enumerate(clips):
            resultado = self.procesar_clip(clip, i)
            if resultado:
                resultados.append(resultado)

        log.info("\n" + "=" * 50)
        log.info(f"  COMPLETADO: {len(resultados)}/{len(clips)} clips")
        log.info(f"  Salida: {self.salida_dir}")
        log.info("=" * 50)

        return resultados


def main():
    import sys
    from pathlib import Path

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
