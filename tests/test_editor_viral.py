"""Tests de `editor_viral.py` tras la separacion de responsabilidades.

Cubren la logica pura de geometria y el acceso a archivos/metadatos.
No requieren FFmpeg ni red.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from editor_viral import (  # noqa: E402
    ClipMetadata,
    CatalogoClips,
    calcular_filtro_vertical,
)


class TestCalcularFiltroVertical:
    """La geometria debe seguir produciendo exactamente los mismos filtros que antes."""

    def test_video_horizontal_recorta_el_centro(self) -> None:
        # 1920x1080 -> crop de 607 de ancho, centrado en (1920-607)//2 = 656
        assert (
            calcular_filtro_vertical(1920, 1080)
            == "crop=607:1080:656:0,scale=1080:1920"
        )

    def test_video_cuadrado(self) -> None:
        assert calcular_filtro_vertical(1080, 1080) == "crop=607:1080:236:0,scale=1080:1920"

    def test_video_ya_vertical_9_16_no_recorre_ancho(self) -> None:
        # 720x1280 es exactamente 9:16: el crop ocupa todo el ancho (offset 0)
        assert calcular_filtro_vertical(720, 1280) == "crop=720:1280:0:0,scale=1080:1920"

    def test_video_estrecho_ajusta_alto_y_centra_en_vertical(self) -> None:
        # El alto exige 1080 de ancho pero el video solo tiene 900:
        # se toma todo el ancho y se recorta alto a 1600, centrado en (1920-1600)//2 = 160
        assert calcular_filtro_vertical(900, 1920) == "crop=900:1600:0:160,scale=1080:1920"

    def test_4k_horizontal(self) -> None:
        assert calcular_filtro_vertical(3840, 2160) == "crop=1215:2160:1312:0,scale=1080:1920"

    def test_respetiza_dimensiones_de_salida_personalizadas(self) -> None:
        resultado = calcular_filtro_vertical(1920, 1080, ancho_final=720, alto_final=1280)
        assert resultado.endswith("scale=720:1280")
        assert resultado.startswith("crop=607:1080:656:0,")

    def test_escala_ancho_crop_proporcional_al_alto(self) -> None:
        for alto in (720, 1080, 1440, 2160):
            filtro = calcular_filtro_vertical(4000, alto)
            ancho_crop = int(filtro.split(",")[0].split(":")[0].removeprefix("crop="))
            assert ancho_crop == int(alto * 1080 / 1920)

    @pytest.mark.parametrize("ancho,alto", [(0, 1080), (1920, 0), (-1, 1080)])
    def test_dimensiones_invalidas_explotan(self, ancho: int, alto: int) -> None:
        with pytest.raises(ValueError):
            calcular_filtro_vertical(ancho, alto)


class TestCatalogoClips:
    def test_crea_la_carpeta_de_salida(self, tmp_path: Path) -> None:
        clips = tmp_path / "clips"
        salida = tmp_path / "editados"
        clips.mkdir()
        CatalogoClips(str(clips), str(salida))
        assert salida.is_dir()

    def test_lista_clips_ordenado_y_sin_otras_extensiones(self, tmp_path: Path) -> None:
        clips = tmp_path / "clips"
        clips.mkdir()
        for nombre in ("clip_2.mp4", "clip_1.mp4", "notas.txt"):
            (clips / nombre).write_bytes(b"x")
        catalogo = CatalogoClips(str(clips), str(tmp_path / "salida"))
        assert [c.name for c in catalogo.listar()] == ["clip_1.mp4", "clip_2.mp4"]

    def test_ruta_salida_usa_sufijo_vertical(self, tmp_path: Path) -> None:
        catalogo = CatalogoClips(str(tmp_path), str(tmp_path / "salida"))
        assert catalogo.ruta_salida("clip_1").name == "clip_1_vertical.mp4"

    def test_metadatos_desde_clips_info(self, tmp_path: Path) -> None:
        clips = tmp_path / "clips"
        clips.mkdir()
        (clips / "clips_info.json").write_text(
            json.dumps(
                [
                    {"titulo_sugerido": "Momento clave", "criterio_principal": "revelación"},
                    {"otra_clave": 1},
                ]
            ),
            encoding="utf-8",
        )
        catalogo = CatalogoClips(str(clips), str(tmp_path / "salida"))
        assert catalogo.metadatos(0) == ClipMetadata("Momento clave", "revelación")
        # indice presente pero sin las claves -> vacios
        assert catalogo.metadatos(1) == ClipMetadata("", "")

    def test_metadatos_tolerantes_sin_archivo_o_fuera_de_rango(self, tmp_path: Path) -> None:
        catalogo = CatalogoClips(str(tmp_path), str(tmp_path / "salida"))
        assert catalogo.metadatos(0) == ClipMetadata("", "")

        (tmp_path / "clips_info.json").write_text(json.dumps([]), encoding="utf-8")
        assert catalogo.metadatos(3) == ClipMetadata("", "")

    def test_metadatos_tolerante_con_json_malformado(self, tmp_path: Path) -> None:
        (tmp_path / "clips_info.json").write_text("{no es json valido", encoding="utf-8")
        catalogo = CatalogoClips(str(tmp_path), str(tmp_path / "salida"))
        assert catalogo.metadatos(0) == ClipMetadata("", "")
