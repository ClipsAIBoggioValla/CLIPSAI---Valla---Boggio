"""Fase 3 de cobertura — routers `backend/api/routes/retrim.py` y `stream.py`,
CLI `app/cli.py` y el branch de migraciones del lifespan de `main.py`.

Todo sin FFmpeg ni PostgreSQL reales: subprocess y SessionLocal mockeados.
"""

from __future__ import annotations

import uuid as uuid_lib
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from _fixtures import FakeResult, FakeSession, make_job

from backend_fastapi.app import cli as cli_mod

def _aux_assert_as_seconds_numericos() -> None:
    assert cli_mod._as_seconds(12) == 12.0
    assert cli_mod._as_seconds(1.5) == pytest.approx(1.5)
    assert cli_mod._as_seconds("12.5") == pytest.approx(12.5)


def _aux_assert_as_seconds_hms() -> None:
    assert cli_mod._as_seconds("00:01:05") == pytest.approx(65.0)
    assert cli_mod._as_seconds("2:30") == pytest.approx(150.0)
    with pytest.raises(ValueError, match="Timestamp inválido"):
        cli_mod._as_seconds("1:2:3:4")


# ---------------------------------------------------------------------- CLI


class TestCliHelpers:
    def test_as_seconds(self) -> None:
        _aux_assert_as_seconds_numericos()
        _aux_assert_as_seconds_hms()

    def test_build_parser(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(["run", "--video", "x.mp4"])
        assert args.handler is cli_mod.command_run
        args = parser.parse_args(["inspect", "--job-id", "abc"])
        assert args.handler is cli_mod.command_inspect
        args = parser.parse_args(["list"])
        assert args.handler is cli_mod.command_list


class TestCliRun:
    def test_video_inexistente(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            cli_mod.run_video(str(tmp_path / "fantasma.mp4"))

    def test_run_video_completo(self, tmp_path, monkeypatch) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"v")
        dest = tmp_path / "clips"
        dest.mkdir()
        monkeypatch.setenv("STORAGE_CLIPS_DIR", str(dest))
        result = {
            "clips": [
                {"title": "a", "inicio": 5.0, "fin": 30.0, "hook_selection": None},
                "no-es-dict",  # se omite con warning
            ],
            "transcription_segments": [{"start": 5, "end": 30, "text": "s"}],
        }

        def _render(video, start, end, segs, hook, job_id, idx, title):
            salida = dest / f"{job_id}_{idx:02d}.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "cut"}

        with (
            patch("backend_fastapi.app.services.engine.run_clip_engine", Mock(return_value=result)),
            patch("backend_fastapi.app.routers.jobs._render_clip_with_ass_and_hook", Mock(side_effect=_render)),
            patch("backend_fastapi.app.routers.jobs._select_hook_for_clip", Mock(return_value=None)),
        ):
            generados = cli_mod.run_video(str(archivo))
        assert len(generados) == 1

    def test_run_video_sin_clips(self, tmp_path) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"v")
        with patch("backend_fastapi.app.services.engine.run_clip_engine", Mock(return_value={"clips": []})):
            with pytest.raises(RuntimeError, match="no devolvió clips"):
                cli_mod.run_video(str(archivo))

    def test_run_video_con_timestamps_invalidos(self, tmp_path) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"v")
        result = {"clips": [{"inicio": 30.0, "fin": 10.0}]}
        with (
            patch("backend_fastapi.app.services.engine.run_clip_engine", Mock(return_value=result)),
            patch("backend_fastapi.app.routers.jobs._select_hook_for_clip", Mock(return_value=None)),
        ):
            with pytest.raises(ValueError, match="timestamps inválidos"):
                cli_mod.run_video(str(archivo))

    def test_run_video_sin_archivos_generados(self, tmp_path) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"v")
        result = {"clips": [{"inicio": 5.0, "fin": 30.0}]}
        with (
            patch("backend_fastapi.app.services.engine.run_clip_engine", Mock(return_value=result)),
            patch("backend_fastapi.app.routers.jobs._render_clip_with_ass_and_hook", Mock(side_effect=RuntimeError("x"))),
            patch("backend_fastapi.app.routers.jobs._select_hook_for_clip", Mock(return_value=None)),
        ):
            with pytest.raises(RuntimeError):
                cli_mod.run_video(str(archivo))

    def test_command_run_ok_y_fallo(self, tmp_path, capsys) -> None:
        args = SimpleNamespace(video=str(tmp_path / "no-existe.mp4"))
        assert cli_mod.command_run(args) == 1
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"v")
        args2 = SimpleNamespace(video=str(archivo))
        with (
            patch("backend_fastapi.app.services.engine.run_clip_engine", Mock(return_value={"clips": []})),
        ):
            assert cli_mod.command_run(args2) == 1

    def test_main_despacha(self, tmp_path, capsys) -> None:
        rc = cli_mod.main(["run", "--video", str(tmp_path / "no-existe.mp4")])
        assert rc == 1


class TestCliInspectList:
    def test_inspect_uuid_invalido(self) -> None:
        args = SimpleNamespace(job_id="no-es-uuid")
        assert cli_mod.command_inspect(args) == 2

    def test_inspect_job_inexistente(self) -> None:
        db = FakeSession()
        args = SimpleNamespace(job_id=str(uuid_lib.uuid4()))
        with patch.object(cli_mod, "SessionLocal", lambda: db):
            assert cli_mod.command_inspect(args) == 1

    def test_inspect_job_completado(self) -> None:
        db = FakeSession()
        job = make_job(uuid_lib.uuid4(), status="completed")
        db.seed(job)
        args = SimpleNamespace(job_id=str(job.id))
        with patch.object(cli_mod, "SessionLocal", lambda: db):
            assert cli_mod.command_inspect(args) == 0

    def test_inspect_job_failed_con_traceback(self, capsys) -> None:
        db = FakeSession()
        job = make_job(uuid_lib.uuid4(), status="failed", result_metadata={"traceback": "TB"})
        db.seed(job)
        args = SimpleNamespace(job_id=str(job.id))
        with patch.object(cli_mod, "SessionLocal", lambda: db):
            assert cli_mod.command_inspect(args) == 0

    def test_inspect_sqlalchemy_error(self) -> None:
        class _DbRota:
            def get(self, *a: Any, **k: Any) -> None:
                raise __import__("sqlalchemy").exc.SQLAlchemyError("db caída")

            def close(self) -> None:
                pass

        args = SimpleNamespace(job_id=str(uuid_lib.uuid4()))
        with patch.object(cli_mod, "SessionLocal", lambda: _DbRota()):
            assert cli_mod.command_inspect(args) == 1

    def test_list_vacio(self) -> None:
        db = FakeSession()
        db.push_result(FakeResult(rows=[]))
        with patch.object(cli_mod, "SessionLocal", lambda: db):
            assert cli_mod.command_list(SimpleNamespace()) == 0

    def test_list_con_jobs(self) -> None:
        db = FakeSession()
        jobs = [make_job(uuid_lib.uuid4(), status="failed", error_message="x " * 50)]
        db.push_result(FakeResult(rows=jobs))
        with patch.object(cli_mod, "SessionLocal", lambda: db):
            assert cli_mod.command_list(SimpleNamespace()) == 0

    def test_list_sqlalchemy_error(self) -> None:
        db = FakeSession()
        db.execute = Mock(side_effect=__import__("sqlalchemy").exc.SQLAlchemyError("db caída"))
        with patch.object(cli_mod, "SessionLocal", lambda: db):
            assert cli_mod.command_list(SimpleNamespace()) == 1


# ------------------------------------------- main.py: lifespan con DB activa


class TestLifespanConDb:
    def test_migraciones_y_huerfanos(self, monkeypatch) -> None:
        from fastapi.testclient import TestClient

        from backend_fastapi.app import database as db_mod
        from backend_fastapi.app.main import app as fastapi_app

        conn = Mock()
        conn.execute = Mock()
        conn.commit = Mock()
        connect_cm = MagicMock()
        connect_cm.__enter__.return_value = conn
        connect_cm.__exit__.return_value = False
        engine = MagicMock()
        engine.connect.return_value = connect_cm

        db = FakeSession()
        job_huerfano = make_job(uuid_lib.uuid4(), status="processing")
        db.query_rows = [job_huerfano]

        cleanup = Mock(return_value=1024 * 1024)
        with (
            patch.object(db_mod, "DB_AVAILABLE", True),
            patch.object(db_mod, "engine", engine),
            patch.object(db_mod, "SessionLocal", lambda: db),
            patch("backend_fastapi.app.services.storage_cleanup.cleanup_storage", cleanup),
        ):
            with TestClient(fastapi_app):
                pass
        # migraciones ejecutadas y commit final
        assert conn.execute.call_count > 20
        conn.commit.assert_called_once()
        # el huérfano quedó marcado como failed
        assert job_huerfano.status == "failed"
        assert "interrumpido" in (job_huerfano.error_message or "")
        cleanup.assert_called_once()

    def test_migraciones_con_db_query_rota(self, monkeypatch) -> None:
        from fastapi.testclient import TestClient

        from backend_fastapi.app import database as db_mod
        from backend_fastapi.app.main import app as fastapi_app

        conn = Mock()
        connect_cm = MagicMock()
        connect_cm.__enter__.return_value = conn
        connect_cm.__exit__.return_value = False
        engine = MagicMock()
        engine.connect.return_value = connect_cm

        class _DbRota:
            def query(self, *a: Any, **k: Any) -> Any:
                raise RuntimeError("query rota")

            def close(self) -> None:
                pass

        cleanup = Mock(return_value=1024 * 1024)
        with (
            patch.object(db_mod, "DB_AVAILABLE", True),
            patch.object(db_mod, "engine", engine),
            patch.object(db_mod, "SessionLocal", lambda: _DbRota()),
            patch("backend_fastapi.app.services.storage_cleanup.cleanup_storage", cleanup),
        ):
            with TestClient(fastapi_app):
                pass
        cleanup.assert_called_once()  # el cleanup corre aunque la limpieza de huérfanos falle
