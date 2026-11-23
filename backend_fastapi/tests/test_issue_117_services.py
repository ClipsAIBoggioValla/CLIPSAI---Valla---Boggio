"""Issue #117 — paridad backend: emojis Noto Color Emoji + zoompan RMS.

Cubre los servicios FastAPI (`ass_generator`, `ffmpeg_service`, `editor`,
`claude_service`) y el plumbing de `routers/jobs.py`. Sin FFmpeg, red ni DB.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.services import ass_generator, claude_service, editor, ffmpeg_service


# ------------------------------------------------------------------ ass_generator


class TestAssEmoji:
    def test_prefijo_noto_y_restauracion_dejavu(self) -> None:
        prefijo = ass_generator._prefijo_emoji("🔥")
        assert prefijo == "{\\fnNoto Color Emoji}🔥{\\fnDejaVu Sans} "

    @pytest.mark.parametrize("emoji", [None, "", "none", "NONE"])
    def test_sin_emoji_no_hay_override(self, emoji: str | None) -> None:
        assert ass_generator._prefijo_emoji(emoji) == ""

    def test_emoji_inseguro_se_sanea(self) -> None:
        assert ass_generator._emoji_seguro("🔥{x}\\N") == "🔥xN"

    def test_generate_ass_content_incluye_override(self) -> None:
        contenido = ass_generator.generate_ass_content(
            [{"start": 0.0, "end": 2.0, "text": "hola mundo", "emoji": "🔥"}]
        )
        dialogue = next(l for l in contenido.splitlines() if l.startswith("Dialogue:"))
        assert dialogue.endswith("{\\fnNoto Color Emoji}🔥{\\fnDejaVu Sans} HOLA MUNDO")

    def test_generate_ass_content_sin_emoji_es_plano(self) -> None:
        contenido = ass_generator.generate_ass_content(
            [{"start": 0.0, "end": 2.0, "text": "hola", "emoji": None}]
        )
        assert "\\fnNoto" not in contenido

    def test_generate_hooked_ass_conserva_emoji(self, tmp_path: Path) -> None:
        destino = tmp_path / "hooked.ass"
        ass_generator.generate_hooked_ass(
            [
                {"start": 5.0, "end": 7.0, "text": "hook", "emoji": "🔥"},
                {"start": 12.0, "end": 14.0, "text": "cuerpo", "emoji": "😱"},
            ],
            clip_start=0.0,
            clip_end=30.0,
            hook_start=5.0,
            hook_end=10.0,
            output_path=destino,
        )
        contenido = destino.read_text(encoding="utf-8")
        assert "{\\fnNoto Color Emoji}🔥{\\fnDejaVu Sans}" in contenido
        assert "{\\fnNoto Color Emoji}😱{\\fnDejaVu Sans}" in contenido


# ------------------------------------------------------------------ ffmpeg_service


class TestFfmpegZoompan:
    def test_sin_picos_devuelve_filtro_vacio(self) -> None:
        assert ffmpeg_service._filtro_zoompan([]) == ""

    def test_expresion_usa_it_fps_y_d1(self) -> None:
        filtro = ffmpeg_service._filtro_zoompan([1.0])
        assert filtro.startswith("fps=30,zoompan=")
        assert "it-1.000" in filtro
        assert "1+0.12" in filtro
        assert ":d=1:" in filtro
        assert ":fps=30" in filtro
        assert ":s=1080x1920" in filtro
        assert "(t-" not in filtro

    def test_max_lleva_segundo_argumento_para_ffmpeg(self) -> None:
        filtro = ffmpeg_service._filtro_zoompan([1.0])
        assert "max(clip(" in filtro
        assert ",0)'" in filtro

    def test_top_k_acota_la_expresion(self) -> None:
        filtro = ffmpeg_service._filtro_zoompan([float(i) for i in range(20)])
        assert filtro.count("clip((it-") == ffmpeg_service.ZOOM_TOP_K


# ------------------------------------------------------------------ editor


class TestEditorReframe:
    def test_sin_picos_no_agrega_zoompan(self) -> None:
        filtro = editor._filtro_reframe()
        assert "zoompan" not in filtro
        assert filtro.endswith(",setsar=1")

    def test_con_picos_ordena_crop_scale_zoom_setsar(self) -> None:
        filtro = editor._filtro_reframe([1.0])
        assert filtro.startswith("crop=")
        assert filtro.index("scale=1080:1920") < filtro.index("fps=30,zoompan=")
        assert filtro.index("fps=30,zoompan=") < filtro.index("setsar=1")
        assert filtro.count("zoompan=") == 1
        assert filtro.endswith(",setsar=1")

    def test_comando_incluye_picos_en_el_vf(self) -> None:
        comando = editor._comando_reframe(Path("in.mp4"), Path("out.mp4"), [2.0])
        vf = comando[comando.index("-vf") + 1]
        assert "fps=30,zoompan=" in vf
        assert "it-2.000" in vf

    def test_reframe_video_propaga_picos(self, tmp_path: Path) -> None:
        origen = tmp_path / "in.mp4"
        origen.write_bytes(b"v")
        salida = tmp_path / "out.mp4"
        ok = SimpleNamespace(returncode=0, stdout="1080x1920", stderr="")
        with (
            patch.object(editor, "_copiar_si_ya_vertical", return_value=False),
            patch.object(editor, "_ejecutar_ffmpeg_reframe", return_value=ok) as ejecutar,
            patch.object(editor, "_validar_salida_reframe"),
            patch.object(editor, "_sondear_salida", return_value=ok),
            patch.object(editor, "_validar_dimensiones_salida"),
        ):
            resultado = editor.reframe_video(origen, salida, picos=[0.5, 2.0])
        assert resultado == str(salida)
        assert ejecutar.call_args.args[3] == [0.5, 2.0]


# ------------------------------------------------------------------ claude_service


def _clip_valido(**overrides: object) -> dict:
    clip = {
        "start_sentence_id": "S_1",
        "end_sentence_id": "S_2",
        "score": 8,
        "title": "Clip de prueba",
        "hook_candidates": [],
        "has_hook": False,
    }
    clip.update(overrides)
    return clip


class TestClaudeEmojiSchema:
    def test_schema_declara_emojis_opcionales(self) -> None:
        schema = claude_service._build_output_schema(["S_1"])
        item = schema["properties"]["clips"]["items"]
        assert "emojis" not in item["required"]
        emojis = item["properties"]["emojis"]
        assert emojis["maxItems"] == 5
        assert set(emojis["items"]["properties"]) == {"segundo", "emoji"}

    def test_sanitiza_invalidos_none_y_caps(self) -> None:
        entradas = [
            {"segundo": 1.5, "emoji": "🔥"},
            {"segundo": "no-numero", "emoji": "😱"},
            {"segundo": 2.0, "emoji": "none"},
            {"segundo": -1.0, "emoji": "😱"},
            {"segundo": 3.0, "emoji": "{x}\\"},
            "no-es-dict",
            {"segundo": 4.0, "emoji": "😂"},
            {"segundo": 5.0, "emoji": "😍"},
            {"segundo": 6.0, "emoji": "🤯"},
            {"segundo": 7.0, "emoji": "💪"},
        ]
        assert claude_service._emojis_validos(entradas) == [
            {"segundo": 1.5, "emoji": "🔥"},
            {"segundo": 3.0, "emoji": "x"},
            {"segundo": 4.0, "emoji": "😂"},
            {"segundo": 5.0, "emoji": "😍"},
            {"segundo": 6.0, "emoji": "🤯"},
        ]

    def test_no_lista_devuelve_vacio(self) -> None:
        assert claude_service._emojis_validos({"segundo": 1.0, "emoji": "🔥"}) == []

    def test_validar_clip_candidato_propaga_emojis(self) -> None:
        validado = claude_service._validar_clip_candidato(
            _clip_valido(emojis=[{"segundo": 12.5, "emoji": "🔥"}, {"segundo": -2, "emoji": "x"}])
        )
        assert validado is not None
        assert validado["emojis"] == [{"segundo": 12.5, "emoji": "🔥"}]

    def test_validar_clip_sin_emojis_devuelve_lista(self) -> None:
        validado = claude_service._validar_clip_candidato(_clip_valido())
        assert validado is not None
        assert validado["emojis"] == []


# ------------------------------------------------------------------ jobs


SEGS_ABS = [
    {"start": 10.0, "end": 12.0, "text": "a"},
    {"start": 12.0, "end": 15.0, "text": "b"},
]


class TestJobsEmoji:
    def test_emojis_en_ventana_excluye_el_fin(self) -> None:
        emojis = [{"segundo": 9.0}, {"segundo": 10.0}, {"segundo": 14.99}, {"segundo": 15.0}]
        assert jobs_router._emojis_en_ventana(emojis, 10.0, 15.0) == [
            {"segundo": 10.0},
            {"segundo": 14.99},
        ]

    def test_emoji_en_segmento_respeta_limites(self) -> None:
        seg = {"start": 12.0, "end": 15.0}
        assert jobs_router._emoji_en_segmento(seg, [{"segundo": 12.0, "emoji": "🔥"}]) == "🔥"
        assert jobs_router._emoji_en_segmento(seg, [{"segundo": 15.0, "emoji": "🔥"}]) is None

    def test_asigna_emoji_solo_al_segmento_que_corresponde(self) -> None:
        emojis = [{"segundo": 13.0, "emoji": "🔥"}]
        resultado = jobs_router._emojis_a_segmentos(SEGS_ABS, emojis, 10.0, 15.0)
        assert resultado[0] == SEGS_ABS[0]
        assert resultado[1] == {**SEGS_ABS[1], "emoji": "🔥"}

    def test_sin_emojis_devuelve_los_mismos_segmentos(self) -> None:
        assert jobs_router._emojis_a_segmentos(SEGS_ABS, [], 10.0, 15.0) is SEGS_ABS

    def test_segmento_shift_conserva_emoji(self) -> None:
        seg = {"start": 13.0, "end": 16.0, "text": "b", "emoji": "🔥"}
        assert jobs_router._segmento_shift(seg, 10.0, 15.0) == {
            "start": 3.0,
            "end": 5.0,
            "text": "b",
            "emoji": "🔥",
        }

    def test_parsear_clip_item_propaga_emojis(self) -> None:
        emojis = [{"segundo": 12.0, "emoji": "🔥"}]
        item = {"title": "Clip", "start": 10.0, "end": 40.0, "score": 8, "emojis": emojis}
        datos = jobs_router._parsear_clip_item(item, 0)
        assert datos["emojis"] == emojis
        assert jobs_router._parsear_clip_item({"start": 0.0}, 1)["emojis"] == []

    def test_ass_simple_quema_el_emoji(self, tmp_path: Path) -> None:
        destino = tmp_path / "clip.ass"
        jobs_router._ass_simple(
            10.0,
            15.0,
            [{"start": 11.0, "end": 12.0, "text": "hola", "emoji": "🔥"}],
            destino,
            None,
        )
        contenido = destino.read_text(encoding="utf-8")
        assert "{\\fnNoto Color Emoji}🔥{\\fnDejaVu Sans} HOLA" in contenido

    def test_render_pasa_emojis_al_generador_ass(self, tmp_path: Path) -> None:
        video = tmp_path / "source.mp4"
        video.write_bytes(b"v")
        capturado: dict = {}

        def _fake_ass(clip_start, clip_end, segments, hook_sel, hook_mode, clip_title):
            capturado["segments"] = segments
            return None

        with (
            patch.object(jobs_router, "STORAGE_CLIPS_DIR", tmp_path / "clips"),
            patch.object(jobs_router, "_generar_ass", side_effect=_fake_ass),
            patch.object(jobs_router, "_cortar_clip_intermedio"),
            patch.object(jobs_router, "_exigir_trimmed_valido"),
            patch.object(jobs_router, "_reframar_y_quemar"),
        ):
            jobs_router._render_clip_with_ass_and_hook(
                str(video), 10.0, 15.0, SEGS_ABS, None, uuid.uuid4(), 0, "Clip",
                emojis=[{"segundo": 13.0, "emoji": "🔥"}],
            )
        assert capturado["segments"][1]["emoji"] == "🔥"
        assert "emoji" not in capturado["segments"][0]
