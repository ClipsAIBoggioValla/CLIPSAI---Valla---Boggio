"""Fase 3 de cobertura — restos de `routers/jobs.py` (Fase 3, Issue 3 de
`ISSUES_CALIDAD_PENDIENTES.md`).

Cubre: `_render_clip_with_ass_and_hook` (con FFmpeg/ASS mockeados), rutas de
resiliencia de `_run_job` (flush roto, commits rotos, metadata rota, segmentos
de fallback, stats de render, hook roto), `run_job_safely` (wrapper), y
`create_job`/`get_job` llamados directo. Sin procesos ni red reales.
"""

from __future__ import annotations

import sys
import uuid as uuid_lib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
from _fixtures import FakeSession, make_job, make_usuario, make_video

from backend_fastapi.app.routers import jobs as jobs_router

ENGINE_PATH = "backend_fastapi.app.services.engine.run_clip_engine"


# ------------------------------------------------------------------ fixtures


def _video_tmp(tmp_path: Path, user: Any, **overrides: Any) -> Any:
    archivo = tmp_path / "source.mp4"
    archivo.write_bytes(b"video-falso-para-ffprobe")
    video = make_video(user.id, **overrides)
    video.filepath = str(archivo)
    video.file_path = str(archivo)
    video.transcription_filepath = None
    if "transcript" not in overrides:
        video.transcript = "00:00:00 - Hola mundo\n00:00:05 - Mas texto"
    return video


def _job_de(video: Any, **overrides: Any) -> Any:
    return make_job(video.id, status="pending", progress=0, **overrides)


def _clip_payload(**overrides: Any) -> dict:
    base = {
        "title": "Buena esquina",
        "inicio": 5.0,
        "fin": 25.0,
        "score": 9,
        "criterio_principal": "revelación",
        "hook_texto": "Nadie lo esperaba",
    }
    base.update(overrides)
    return base


def _engine_ok(result: Any, callback_pct: int | None = None) -> Mock:
    def _inner(video: str, transcripcion: str, progress_callback=None, **kw: Any):
        if callback_pct is not None and progress_callback is not None:
            progress_callback(callback_pct)
        return result

    return Mock(side_effect=_inner)


def _ejecutar(
    fake_db: FakeSession,
    job: Any,
    engine: Mock,
    *,
    render: Mock | None = None,
    cleanup: Mock | None = None,
    stdout_roto: bool = False,
) -> None:
    """Corre `_run_job` con patches estándar (+ opcionales)."""
    stdout_real = sys.stdout

    class _FlushRoto:
        def flush(self) -> None:
            raise ValueError("flush roto")

        def __getattr__(self, name: str) -> Any:
            return getattr(stdout_real, name)

    patches: list[Any] = [
        patch.object(jobs_router, "SessionLocal", lambda: fake_db),
        patch(ENGINE_PATH, engine),
        patch(
            "backend_fastapi.app.services.storage_cleanup.cleanup_storage",
            cleanup or Mock(return_value=1024 * 1024),
        ),
    ]
    if render is not None:
        patches.append(patch.object(jobs_router, "_render_clip_with_ass_and_hook", render))
    if stdout_roto:
        patches.append(patch.object(sys, "stdout", _FlushRoto()))
    with _patches_apiladas(patches):
        jobs_router._run_job(job.id)  # type: ignore[arg-type]


class _patches_apiladas:
    """Context manager que apila varios patches."""

    def __init__(self, patches: list[Any]) -> None:
        self._patches = patches

    def __enter__(self) -> None:
        for p in self._patches:
            p.__enter__()

    def __exit__(self, *exc: Any) -> None:
        for p in reversed(self._patches):
            p.__exit__(*exc)


class _CommitFailSession(FakeSession):
    """FakeSession cuyo `commit()` falla a partir de la N-ésima llamada."""

    def __init__(self, fail_from: int = 2) -> None:
        super().__init__()
        self._n = 0
        self.fail_from = fail_from

    def commit(self) -> None:
        self._n += 1
        if self._n >= self.fail_from:
            raise RuntimeError("commit roto")
        return super().commit()


def _job_stub(video: Any, *, metadata_rota: bool = False) -> Any:
    """Stub con __name__ 'Job' para que FakeSession.get lo encuentre."""
    base: dict[str, Any] = {
        "id": uuid_lib.uuid4(),
        "video_id": video.id,
        "status": "pending",
        "progress": 0,
        "error_message": None,
    }

    cls = type("Job", (), {})
    obj = cls()
    for key, value in base.items():
        setattr(obj, key, value)
    if metadata_rota:

        @property
        def _rm(self: Any) -> dict:
            return {"previo": True}

        @property
        def _rm_set(self: Any) -> None:  # pragma: no cover
            return None

        def _setter(self: Any, value: Any) -> None:
            raise RuntimeError("metadata rota")

        cls.result_metadata = property(lambda self: {"previo": True}, _setter)
    return obj


# ------------------------------------------------- _render_clip_with_ass_and_hook


def _mocks_render(tmp_path: Path, *, burn_crea: bool = True) -> dict[str, Mock]:
    """Mocks de editor/ffmpeg/ass usados por `_render_clip_with_ass_and_hook`."""

    def _crea(dest: Any, contenido: bytes = b"salida") -> None:
        Path(dest).write_bytes(contenido)

    editor = Mock()
    editor.reframe_video = Mock(
        side_effect=lambda src, dst, **kw: _crea(dst, b"reframed-9x16")
    )

    ffmpeg = Mock()
    ffmpeg.cut_segment = Mock(side_effect=lambda src, s, e, out: _crea(out, b"trimmed"))
    ffmpeg.build_hook_clip = Mock(
        side_effect=lambda src, cs, ce, hs, he, out: _crea(out, b"hook+clip")
    )
    if burn_crea:
        ffmpeg.burn_subtitles = Mock(side_effect=lambda inp, ass, out: _crea(out, b"final"))
    else:
        ffmpeg.burn_subtitles = Mock()

    ass = Mock()
    ass.generate_hooked_ass = Mock()
    ass.write_ass_file = Mock()

    return {"editor": editor, "ffmpeg": ffmpeg, "ass": ass}


_PROBE_OK = Mock(
    returncode=0,
    stdout='{"streams": [{"width": 1080, "height": 1920, "duration": "30.0"}]}',
)


class TestRenderClipConAssYHook:
    def _correr(
        self,
        tmp_path: Path,
        mock: dict[str, Mock],
        *,
        clip_start: float = 10.0,
        clip_end: float = 40.0,
        segments: list[dict] | None = None,
        hook_sel: tuple | None = None,
        probe: Mock | None = None,
    ) -> tuple[str, dict]:
        storage = tmp_path / "clips"
        storage.mkdir(exist_ok=True)
        video = tmp_path / "source.mp4"
        video.write_bytes(b"v")
        patches = [
            patch.object(jobs_router, "STORAGE_CLIPS_DIR", storage),
            patch("backend_fastapi.app.services.editor.reframe_video", mock["editor"].reframe_video),
            patch("backend_fastapi.app.services.ffmpeg_service.cut_segment", mock["ffmpeg"].cut_segment),
            patch("backend_fastapi.app.services.ffmpeg_service.build_hook_clip", mock["ffmpeg"].build_hook_clip),
            patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", mock["ffmpeg"].burn_subtitles),
            patch("backend_fastapi.app.services.ass_generator.generate_hooked_ass", mock["ass"].generate_hooked_ass),
            patch("backend_fastapi.app.services.ass_generator.write_ass_file", mock["ass"].write_ass_file),
        ]
        if probe is not None:
            patches.append(patch("subprocess.run", probe))
        with _patches_apiladas(patches):
            return jobs_router._render_clip_with_ass_and_hook(
                str(video),
                clip_start,
                clip_end,
                segments if segments is not None else [{"start": 11.0, "end": 15.0, "text": "gol"}],
                hook_sel,
                uuid_lib.uuid4(),
                0,
                "Titulo",
            )

    def test_teaser_hook_con_ass_y_probe(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        salida, meta = self._correr(
            tmp_path,
            mock,
            hook_sel=(5.0, 8.0, {"mode": "teaser", "text": "hook"}),
            probe=_PROBE_OK,
        )
        assert meta["render"] == "hook+ass"
        assert meta["hook_applied"] and meta["ass_applied"]
        assert meta["hook_mode"] == "teaser"
        assert meta["aspect_ratio"] == "9:16"
        assert Path(salida).is_file()
        mock["ass"].generate_hooked_ass.assert_called_once()
        mock["ffmpeg"].build_hook_clip.assert_called_once()
        mock["ffmpeg"].burn_subtitles.assert_called_once()

    def test_sin_hook_ass_simple(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        _, meta = self._correr(tmp_path, mock, hook_sel=None)
        assert meta["render"] == "ass"
        mock["ass"].write_ass_file.assert_called_once()
        mock["ffmpeg"].cut_segment.assert_called_once()

    def test_sin_segmentos_mueve_el_reframed(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        salida, meta = self._correr(tmp_path, mock, segments=[])
        assert meta["render"] == "cut"
        assert meta["ass_applied"] is False
        assert Path(salida).is_file()

    def test_hook_in_clip_sin_teaser(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        _, meta = self._correr(
            tmp_path, mock, hook_sel=(12.0, 15.0, {"mode": "in_clip"})
        )
        # in_clip no usa build_hook_clip sino cut_segment + ASS simple,
        # pero al haber hook el meta queda "hook+ass"
        mock["ffmpeg"].cut_segment.assert_called_once()
        assert meta["render"] == "hook+ass"
        assert meta["hook_mode"] == "in_clip"

    def test_ass_generation_falla_sigue_sin_ass(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        mock["ass"].generate_hooked_ass = Mock(side_effect=RuntimeError("ass roto"))
        _, meta = self._correr(
            tmp_path, mock, hook_sel=(5.0, 8.0, {"mode": "teaser"})
        )
        assert meta["render"] == "hook"
        assert meta["ass_applied"] is False

    def test_trimmed_vacio_aborta(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        mock["ffmpeg"].cut_segment = Mock()  # no crea el archivo
        with pytest.raises(RuntimeError, match="no existe o está vacío"):
            self._correr(tmp_path, mock)

    def test_reframe_falla_propaga_al_pipeline(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        mock["editor"].reframe_video = Mock(side_effect=RuntimeError("reframe crujio"))
        # el try/finally del render no tiene except: el error original se propaga
        # y lo captura el wrapper global de `_run_job`
        with pytest.raises(RuntimeError, match="reframe crujio"):
            self._correr(tmp_path, mock)

    def test_validaciones_de_argumentos(self, tmp_path: Path) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"x")
        with pytest.raises(ValueError, match="Tiempos negativos"):
            jobs_router._render_clip_with_ass_and_hook(
                str(archivo), -1.0, 30.0, [], None, uuid_lib.uuid4(), 0, None
            )
        with pytest.raises(ValueError, match="fuera de rango"):
            jobs_router._render_clip_with_ass_and_hook(
                str(archivo), 10.0, 11.0, [], None, uuid_lib.uuid4(), 0, None
            )
        with pytest.raises(ValueError, match="entre 2.5 y 5.5"):
            jobs_router._render_clip_with_ass_and_hook(
                str(archivo), 10.0, 30.0, [], (11.0, 12.0, {"mode": "teaser"}), uuid_lib.uuid4(), 0, None
            )

    def test_ruta_de_video_invalida(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Ruta de video vacía"):
            jobs_router._render_clip_with_ass_and_hook(
                "  ", 10.0, 30.0, [], None, uuid_lib.uuid4(), 0, None
            )
        with pytest.raises(FileNotFoundError, match="no encontrado en disco"):
            jobs_router._render_clip_with_ass_and_hook(
                str(tmp_path / "fantasma.mp4"), 10.0, 30.0, [], None, uuid_lib.uuid4(), 0, None
            )
        with pytest.raises(FileNotFoundError, match="no encontrado"):
            jobs_router._render_clip_with_ass_and_hook(
                str(tmp_path), 10.0, 30.0, [], None, uuid_lib.uuid4(), 0, None  # directorio
            )

    def test_video_vacio_solo_advierte_y_renderiza_igual(self, tmp_path: Path) -> None:
        """Comportamiento actual: el check de 0 bytes traga su propio RuntimeError
        (except Exception) → solo advierte y continúa al render mockeado."""
        mock = _mocks_render(tmp_path)
        vacio = tmp_path / "vacio.mp4"
        vacio.write_bytes(b"")
        storage = tmp_path / "clips"
        storage.mkdir(exist_ok=True)
        with _patches_apiladas(
            [
                patch.object(jobs_router, "STORAGE_CLIPS_DIR", storage),
                patch("backend_fastapi.app.services.editor.reframe_video", mock["editor"].reframe_video),
                patch("backend_fastapi.app.services.ffmpeg_service.cut_segment", mock["ffmpeg"].cut_segment),
                patch("backend_fastapi.app.services.ffmpeg_service.build_hook_clip", mock["ffmpeg"].build_hook_clip),
                patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", mock["ffmpeg"].burn_subtitles),
                patch("backend_fastapi.app.services.ass_generator.generate_hooked_ass", mock["ass"].generate_hooked_ass),
                patch("backend_fastapi.app.services.ass_generator.write_ass_file", mock["ass"].write_ass_file),
            ]
        ):
            _, meta = jobs_router._render_clip_with_ass_and_hook(
                str(vacio), 10.0, 30.0, [], None, uuid_lib.uuid4(), 0, None
            )
        assert meta["render"] == "cut"

    def test_stat_con_permiso_denegado_solo_advierte(self, tmp_path: Path) -> None:
        mock = _mocks_render(tmp_path)
        storage = tmp_path / "clips"
        storage.mkdir(exist_ok=True)
        video = tmp_path / "source.mp4"
        video.write_bytes(b"v")
        video_str = str(video)

        def _stat_falso(self: Any, *a: Any, **k: Any) -> Any:
            if str(self) == video_str:
                raise PermissionError("permiso")
            return SimpleNamespace(st_size=100)

        with _patches_apiladas(
            [
                patch.object(jobs_router, "STORAGE_CLIPS_DIR", storage),
                patch("backend_fastapi.app.services.editor.reframe_video", mock["editor"].reframe_video),
                patch("backend_fastapi.app.services.ffmpeg_service.cut_segment", mock["ffmpeg"].cut_segment),
                patch("backend_fastapi.app.services.ffmpeg_service.build_hook_clip", mock["ffmpeg"].build_hook_clip),
                patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", mock["ffmpeg"].burn_subtitles),
                patch("backend_fastapi.app.services.ass_generator.generate_hooked_ass", mock["ass"].generate_hooked_ass),
                patch("backend_fastapi.app.services.ass_generator.write_ass_file", mock["ass"].write_ass_file),
                patch("pathlib.Path.stat", new=_stat_falso),
            ]
        ):
            salida, meta = jobs_router._render_clip_with_ass_and_hook(
                video_str, 10.0, 30.0, [], None, uuid_lib.uuid4(), 0, None
            )
        assert meta["render"] == "cut"


# ------------------------------------------------------------------- _run_job


class TestRunJobFase3:
    def test_callback_whisper_actualiza_progreso(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {
            "clips": [_clip_payload()],
            "transcription_segments": [{"start": 5, "end": 25, "text": "seg"}],
        }
        dest = tmp_path / "renders"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "hook+ass", "hook_applied": True, "ass_applied": True}

        _ejecutar(
            fake_db,
            job,
            _engine_ok(result, callback_pct=35),
            render=Mock(side_effect=fake_render),
        )
        assert job.status == "completed"
        assert fake_db.commits >= 3

    def test_progreso_persiste_aun_si_set_progress_explota(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {"clips": [_clip_payload()], "transcription_segments": [{"start": 5, "end": 25, "text": "s"}]}
        dest = tmp_path / "renders2"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with patch.object(jobs_router, "_set_progress", Mock(side_effect=RuntimeError("db lenta"))):
            _ejecutar(
                fake_db,
                job,
                _engine_ok(result),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"

    def test_sin_transcripcion_y_progreso_roto(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user, transcript=None)
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {"clips": [_clip_payload()]}
        dest = tmp_path / "renders3"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with patch.object(jobs_router, "_set_progress", Mock(side_effect=RuntimeError("roto"))):
            _ejecutar(fake_db, job, _engine_ok(result), render=Mock(side_effect=fake_render))
        assert job.status == "completed"

    def test_settings_de_claude_desde_config(self, tmp_path, user, monkeypatch) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        dest = tmp_path / "renders4"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        settings = SimpleNamespace(anthropic_api_key="sk-ant-1234567890")
        with (
            patch("backend_fastapi.app.config.get_settings", Mock(return_value=settings)),
            patch.object(jobs_router, "_load_transcription_segments", Mock(return_value=[{"start": 5, "end": 10, "text": "x"}])),
        ):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()]}),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"

    def test_settings_de_claude_explota_sigue(self, tmp_path, user, monkeypatch) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        dest = tmp_path / "renders5"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with (
            patch(
                "backend_fastapi.app.config.get_settings",
                Mock(side_effect=RuntimeError("settings roto")),
            ),
            patch.object(jobs_router, "_load_transcription_segments", Mock(return_value=[{"start": 5, "end": 10, "text": "x"}])),
        ):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()]}),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"

    def test_engine_native_claude_loggea_semantico(self, tmp_path, user, monkeypatch) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxxx")
        result = {
            "engine": "native_claude",
            "clips": [_clip_payload(criterio_principal="claude_semantico")],
            "transcription_segments": [{"start": 5, "end": 25, "text": "s"}],
        }
        dest = tmp_path / "renders6"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "hook+ass", "hook_applied": True, "ass_applied": True}

        _ejecutar(fake_db, job, _engine_ok(result), render=Mock(side_effect=fake_render))
        assert job.status == "completed"
        assert job.result_metadata["_render_stats"]["hook+ass"] == 1

    def test_segmentos_malformados_se_descartan(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {
            "clips": [_clip_payload()],
            "transcription_segments": [
                42,
                {"start": "x", "end": 1, "text": "roto"},
                {"start": 1, "end": 2, "text": "   "},
                {"start": 5, "end": 25, "text": "bueno"},
            ],
        }
        dest = tmp_path / "renders7"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "ass", "hook_applied": False, "ass_applied": True}

        _ejecutar(fake_db, job, _engine_ok(result), render=Mock(side_effect=fake_render))
        assert job.result_metadata["_segments_count"] == 1

    def test_engine_devuelve_lista(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders8"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        # result es lista → clips_payload = result; luego result["_render_stats"]
        # falla (TypeError) y se captura — el job igual completa.
        with patch.object(jobs_router, "_load_transcription_segments", Mock(return_value=[{"start": 5, "end": 10, "text": "x"}])):
            _ejecutar(
                fake_db,
                job,
                _engine_ok([_clip_payload()]),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"

    def test_r2_end_invalido_y_score_invalido(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {
            "engine": "native",
            "clips": [
                {
                    "url_r2": "https://videos.clipsai.xyz/clips/v/0.mp4",
                    "titulo": "R2",
                    "inicio": "00:00:05",
                    "fin": "00:00:02",  # end <= start → +30s
                    "score": "no-es-numero",
                }
            ],
        }
        with (
            patch.object(jobs_router, "_set_progress", Mock(side_effect=RuntimeError("x"))),
            patch.object(sys, "stdout", SimpleNamespace(flush=Mock(side_effect=ValueError("no")))),
        ):
            _ejecutar(fake_db, job, _engine_ok(result))
        assert job.status == "completed"
        clip = fake_db.added[0]
        assert clip.end_time - clip.start_time == pytest.approx(30.0)
        assert clip.score is None

    def test_r2_con_flush_roto(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {
            "engine": "native",
            "clips": [
                {
                    "url_r2": "https://videos.clipsai.xyz/clips/v/1.mp4",
                    "titulo": "R2",
                    "inicio": 5,
                    "fin": 30,
                    "score": 8,
                }
            ],
        }
        _ejecutar(fake_db, job, _engine_ok(result), stdout_roto=True)
        assert job.status == "completed"

    def test_load_transcription_explota_render_sin_ass(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user, transcript=None)
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders9"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with patch.object(jobs_router, "_load_transcription_segments", Mock(side_effect=RuntimeError("whisper roto"))):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()]}),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"
        assert job.result_metadata["_ass_hook_enabled"] is False

    def test_parse_transcript_explota_render_sin_ass(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        video.transcription_filepath = None
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders10"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with (
            patch.object(jobs_router, "_load_transcription_segments", Mock(side_effect=RuntimeError("roto"))),
            patch.object(jobs_router, "_parse_transcript_text_to_segments", Mock(side_effect=RuntimeError("parser roto"))),
        ):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()]}),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"
        assert job.result_metadata["_ass_hook_enabled"] is False

    def test_segmentos_fallback_se_usan(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        video.transcription_filepath = None
        job = _job_de(video)
        fake_db.seed(video, job)
        result = {"clips": [_clip_payload()], "transcription_segments": []}
        dest = tmp_path / "renders11"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "ass", "hook_applied": False, "ass_applied": True}

        with patch.object(
            jobs_router,
            "_load_transcription_segments",
            Mock(return_value=[{"start": 5, "end": 10, "text": "fallback"}]),
        ):
            _ejecutar(fake_db, job, _engine_ok(result), render=Mock(side_effect=fake_render))
        assert job.status == "completed"
        assert job.result_metadata["_segments_count"] == 1

    def test_stats_de_render_por_tipo(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders12"
        dest.mkdir()
        clips = [
            _clip_payload(title="a", inicio=0, fin=20),
            _clip_payload(title="b", inicio=0, fin=20),
            _clip_payload(title="c", inicio=0, fin=20),
            _clip_payload(title="d", inicio=0, fin=20),
            _clip_payload(title="e", inicio=0, fin=20),
        ]
        metas = [
            {"render": "ass", "hook_applied": False, "ass_applied": True},
            {"render": "hook", "hook_applied": True, "ass_applied": False},
            {"render": "cut"},
            {"render": "raro"},  # fallback
            {"render": "hook+ass", "hook_applied": True, "ass_applied": True},
        ]
        salidas = [dest / f"clip_{i}.mp4" for i in range(5)]

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            idx = salidas.index(Path(args[5])) if False else len(list(dest.glob("clip_*.mp4")))
            salida = salidas[idx]
            salida.write_bytes(b"r")
            return str(salida), metas[idx]

        with (
            patch.object(jobs_router, "_set_progress", Mock(side_effect=RuntimeError("x"))),
            patch.object(jobs_router, "_select_hook_for_clip", Mock(return_value=None)),  # SIN hook → rama 917
        ):
            _ejecutar(fake_db, job, _engine_ok({"clips": clips}), render=Mock(side_effect=fake_render))
        stats = job.result_metadata["_render_stats"]
        assert stats["ass"] == 1
        assert stats["hook"] == 1
        assert stats["cut"] == 1
        assert stats["fallback"] == 1
        assert stats["hook+ass"] == 1

    def test_items_raros_se_salten_o_clampean(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders13"
        dest.mkdir()
        clips = [
            _clip_payload(title="corto", inicio=0, fin=1),  # duración 1 → clamp a 30
            _clip_payload(title="score-malo", score="abc"),
            _clip_payload(title="tags-raros", tags="una-tag"),
            _clip_payload(title="tags-lista", tags=["t1", "t2"]),
            {"title": "storage-raro", "inicio": 0, "fin": 20, "score": 9, "storage_path": 123},
        ]

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            n = len(list(dest.glob("clip_*.mp4")))
            salida = dest / f"clip_{n}.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with (
            patch.object(jobs_router, "_set_progress", Mock(side_effect=RuntimeError("x"))),
            patch.object(sys, "stdout", SimpleNamespace(flush=Mock(side_effect=ValueError("no")))),
        ):
            _ejecutar(fake_db, job, _engine_ok({"clips": clips}), render=Mock(side_effect=fake_render))
        assert job.status == "completed"
        assert len(fake_db.added) == 5
        por_titulo = {c.title: c for c in fake_db.added}
        assert por_titulo["corto"].end_time - por_titulo["corto"].start_time == pytest.approx(30.0)
        assert por_titulo["score-malo"].score is None
        assert por_titulo["tags-raros"].tags["_raw_tags"] == ["una-tag"]
        assert por_titulo["tags-lista"].tags["_raw_tags"] == ["t1", "t2"]
        # storage_path no-str se coerciona a str (línea 925) aunque el render lo reemplace
        assert por_titulo["storage-raro"].storage_path.endswith("clip_4.mp4")

    def test_hook_selector_explota_usa_fallback(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders14"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "hook", "hook_applied": True, "ass_applied": False}

        with patch.object(jobs_router, "_select_hook_for_clip", Mock(side_effect=RuntimeError("hook roto"))):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()], "transcription_segments": [{"start": 5, "end": 25, "text": "s"}]}),
                render=Mock(side_effect=fake_render),
            )
        clip = fake_db.added[0]
        assert clip.tags["hook"]["source"] == "in_clip_fallback"

    def test_render_devuelve_path_inexistente_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        _ejecutar(
            fake_db,
            job,
            _engine_ok({"clips": [_clip_payload()], "transcription_segments": [{"start": 5, "end": 25, "text": "s"}]}),
            render=Mock(return_value=("/no/existe/clip.mp4", {"render": "cut"})),
        )
        assert job.status == "failed"

    def test_engine_borra_el_video_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)

        def _borra_y_devuelve(*a: Any, **kw: Any) -> dict:
            Path(video.filepath).unlink()
            return {"clips": [_clip_payload()]}

        _ejecutar(fake_db, job, Mock(side_effect=_borra_y_devuelve))
        assert job.status == "failed"
        assert "no se puede renderizar" in (job.error_message or "")

    def test_error_corto_expandido_y_indexerror(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        _ejecutar(fake_db, job, Mock(side_effect=RuntimeError("4")))
        assert job.status == "failed"
        # el mensaje spec ("| Details:") se preserva; lo expandido queda en metadata
        assert "Posibles causas" in (job.result_metadata["error"] or "")

        fake_db2 = FakeSession()
        video2 = _video_tmp(tmp_path, user)
        job2 = _job_de(video2)
        fake_db2.seed(video2, job2)
        _ejecutar(fake_db2, job2, Mock(side_effect=IndexError("segments: list index out of range")))
        assert "No se detectaron segmentos de audio" in (job2.result_metadata["error"] or "")

    def test_metadata_rota_falla_igual_a_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_stub(video, metadata_rota=True)
        fake_db.seed(video, job)
        _ejecutar(fake_db, job, Mock(side_effect=RuntimeError("boom genérico")))
        assert job.status == "failed"
        assert "boom genérico" in (job.error_message or "")

    def test_commits_rotos_marcan_failed_igual(self, tmp_path, user) -> None:
        fake_db = _CommitFailSession(fail_from=2)
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        _ejecutar(fake_db, job, Mock(side_effect=RuntimeError("boom con commit roto")))
        assert job.status == "failed"

    def test_set_progress_con_db_rota_y_cleanup_roto(self, monkeypatch) -> None:
        artificial = SimpleNamespace(id=uuid_lib.uuid4(), progress=0)
        fake_db = FakeSession()
        fake_db.refresh = Mock(side_effect=RuntimeError("refresh roto"))
        fake_db.commit_error = RuntimeError("commit roto")
        assert jobs_router._set_progress(fake_db, artificial, 40) is None

        artificial2 = SimpleNamespace(id=uuid_lib.uuid4(), progress=0)
        fake_db2 = FakeSession()
        fake_db2.commit_error = RuntimeError("commit roto")
        fake_db2.rollback = Mock()
        assert jobs_router._set_progress(fake_db2, artificial2, 40) is None
        fake_db2.rollback.assert_called()

    def test_transcription_en_disco_inexistente_usa_bd(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        video.transcription_filepath = str(tmp_path / "ya-no-existe.txt")
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders15"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with patch.object(
            jobs_router, "_load_transcription_segments", Mock(return_value=[{"start": 5, "end": 10, "text": "x"}])
        ):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()]}),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"

    def test_transcription_completamente_ausente_igual_procesa(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user, transcript=None)
        video.transcription_filepath = None
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders16"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with patch.object(
            jobs_router, "_load_transcription_segments", Mock(return_value=[{"start": 5, "end": 10, "text": "x"}])
        ):
            _ejecutar(
                fake_db,
                job,
                _engine_ok({"clips": [_clip_payload()]}),
                render=Mock(side_effect=fake_render),
            )
        assert job.status == "completed"

    def test_transcription_inexistente_y_sin_bd_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user, transcript=None)
        video.transcription_filepath = str(tmp_path / "fantasma.txt")
        job = _job_de(video)
        fake_db.seed(video, job)
        engine = Mock()
        _ejecutar(fake_db, job, engine)
        engine.assert_not_called()
        assert job.status == "failed"
        assert "Transcripción no encontrada" in (job.error_message or "")

    def test_cleanup_post_job_explota_silencio(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        dest = tmp_path / "renders17"
        dest.mkdir()

        def fake_render(*args: Any, **kw: Any) -> tuple[str, dict]:
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        _ejecutar(
            fake_db,
            job,
            _engine_ok({"clips": [_clip_payload()]}),
            render=Mock(side_effect=fake_render),
            cleanup=Mock(side_effect=RuntimeError("cleanup roto")),
        )
        assert job.status == "completed"


# ------------------------------------------------------------- run_job_safely


class TestRunJobSafelyFase3:
    def test_job_id_invalido_no_explota(self, monkeypatch) -> None:
        with (
            patch.object(jobs_router, "SessionLocal", lambda: FakeSession()),
            patch("backend_fastapi.app.database.SessionLocal", lambda: FakeSession()),
        ):
            import asyncio

            asyncio.run(jobs_router.run_job_safely("no-es-un-uuid"))

    def test_wrapper_marca_failed_con_job_encontrado(self, tmp_path, user) -> None:
        import asyncio

        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        with (
            patch.object(jobs_router, "SessionLocal", lambda: fake_db),
            # run_job_safely importa SessionLocal desde ..database (no del módulo)
            patch("backend_fastapi.app.database.SessionLocal", lambda: fake_db),
            patch.object(jobs_router, "_run_job", Mock(side_effect=RuntimeError("pipeline murió"))),
        ):
            asyncio.run(jobs_router.run_job_safely(job.id))
        assert job.status == "failed"
        assert "pipeline murió" in (job.error_message or "")

    def test_wrapper_con_stdout_y_cleanup_rotos(self, tmp_path, user) -> None:
        import asyncio

        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_de(video)
        fake_db.seed(video, job)
        stdout_real = sys.stdout

        class _FlushRoto:
            def flush(self) -> None:
                raise ValueError("no")

            def __getattr__(self, name: str) -> Any:
                return getattr(stdout_real, name)

        with (
            patch.object(jobs_router, "SessionLocal", lambda: fake_db),
            patch("backend_fastapi.app.database.SessionLocal", lambda: fake_db),
            patch.object(jobs_router, "_run_job", Mock(side_effect=RuntimeError("x"))),
            patch.object(sys, "stdout", _FlushRoto()),
            patch(
                "backend_fastapi.app.services.storage_cleanup.cleanup_storage",
                Mock(side_effect=RuntimeError("cleanup roto")),
            ),
        ):
            asyncio.run(jobs_router.run_job_safely(job.id))
        assert job.status == "failed"


# ------------------------------------------------------------- create/get job


class TestEndpointsJobsDirectos:
    def test_create_job_con_background_tasks_roto_usa_fallback(self, db, user) -> None:
        from backend_fastapi.app.models import Video as VideoModel
        from backend_fastapi.app.routers.jobs import create_job

        video = make_video(user.id)
        db.seed(video)
        bg = Mock()
        bg.add_task = Mock(side_effect=[RuntimeError("bg roto"), None])

        creado = create_job(video.id, db, user, bg)
        assert creado.status == "pending"
        assert bg.add_task.call_count == 2
        assert bg.add_task.call_args_list[1].args[0] is jobs_router._run_job

    def test_get_job_video_de_otro_usuario_404(self, db, user) -> None:
        import pytest as _pytest
        from fastapi import HTTPException

        from backend_fastapi.app.routers.jobs import get_job

        otro = make_usuario()
        video = make_video(otro.id)
        job = make_job(video.id)
        db.seed(job, video)
        with _pytest.raises(HTTPException) as exc:
            get_job(job.id, db, user)
        assert exc.value.status_code == 404
