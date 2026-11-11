"""Fase 3 de cobertura — routers `backend/api/routes/retrim.py` y `stream.py`,
CLI `app/cli.py` y el branch de migraciones del lifespan de `main.py`.

Todo sin FFmpeg ni PostgreSQL reales: subprocess y SessionLocal mockeados.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import uuid as uuid_lib
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

import _fixtures
from _fixtures import FakeResult, FakeSession, make_clip, make_job, make_usuario, make_video

from backend.api.routes import retrim as retrim_mod
from backend.api.routes import stream as stream_mod
from backend.api.routes.stream import _to_event
from backend_fastapi.app import cli as cli_mod

# ------------------------------------------------------------------- retrim


class TestRetrim:
    def _db(self, user: Any, *, clip: Any | None = None, video: Any | None = None, job: Any | None = None) -> FakeSession:
        db = FakeSession()
        video = video or make_video(user.id)
        job = job or make_job(video.id)
        clip = clip or make_clip(job.id, video.id)
        # retrim hace hasattr(clip.video / job.video) — evitar AttributeError
        clip.video = None
        job.video = None
        db.seed(clip, job, video)
        return db

    @contextlib.contextmanager
    def _configurar(
        self,
        client,
        db: FakeSession,
        user: Any,
        *,
        clip: Any = None,
        video: Any = None,
        job: Any = None,
    ) -> Any:
        """Conecta el FakeSession a la app y devuelve el cliente listo."""
        from backend_fastapi.app.deps import get_current_user, get_db
        from backend_fastapi.app.main import app

        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    def _pushes_dueno(self, db: FakeSession, user: Any, clip: Any, job: Any, video: Any) -> None:
        # retrim hace hasattr(clip.video / job.video) y lee video.filepath — evitar AttributeError
        clip.video = None
        job.video = None
        video.filepath = None
        # orden de selects en retrim_clip: clip, job, video, job, video
        db.push_result(FakeResult(scalar=clip))
        for _ in range(2):
            db.push_result(FakeResult(scalar=job))
            db.push_result(FakeResult(scalar=video))

    def test_body_invalido_422(self, client, db, user) -> None:
        for cuerpo in (
            {"start_time": 30.0, "end_time": 10.0},
            {"start_time": 10.0, "end_time": 12.0},
            {"start_time": 0.0, "end_time": 120.0},
        ):
            with self._configurar(client, db, user):
                r = client.post(f"/clips/{uuid_lib.uuid4()}/retrim", json=cuerpo)
            assert r.status_code == 422

    def test_clip_id_invalido_422(self, client, db, user) -> None:
        with self._configurar(client, db, user):
            r = client.post("/clips/no-es-uuid/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 422

    def test_clip_inexistente_404(self, client, db, user) -> None:
        db.push_result(FakeResult(scalar=None))
        with self._configurar(client, db, user):
            r = client.post(f"/clips/{uuid_lib.uuid4()}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 404

    def test_job_inexistente_404(self, client, db, user) -> None:
        clip = make_clip(uuid_lib.uuid4())
        db.push_result(FakeResult(scalar=clip))  # clip
        db.push_result(FakeResult(scalar=None))  # job
        with self._configurar(client, db, user):
            r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 404

    def test_video_de_otro_usuario_404(self, client, db, user) -> None:
        otro = make_usuario()
        video = make_video(otro.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id)
        db.push_result(FakeResult(scalar=clip))
        db.push_result(FakeResult(scalar=job))
        db.push_result(FakeResult(scalar=video))
        with self._configurar(client, db, user):
            r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 404

    def test_ffmpeg_falla_500(self, client, db, user, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id, storage_path=str(tmp_path / "source.mp4"))
        (tmp_path / "source.mp4").write_bytes(b"v")
        self._pushes_dueno(db, user, clip, job, video)
        fallo = SimpleNamespace(returncode=1, stderr=b"invalid data")
        with self._configurar(client, db, user):
            with patch("backend.api.routes.retrim.subprocess.run", Mock(return_value=fallo)):
                r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 500
        assert "re-trim falló" in r.json()["detail"]

    def test_ffmpeg_timeout_504(self, client, db, user, tmp_path, monkeypatch) -> None:
        import subprocess as _sp

        monkeypatch.chdir(tmp_path)
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id, storage_path=str(tmp_path / "source.mp4"))
        (tmp_path / "source.mp4").write_bytes(b"v")
        self._pushes_dueno(db, user, clip, job, video)
        with self._configurar(client, db, user):
            with patch("backend.api.routes.retrim.subprocess.run", Mock(side_effect=_sp.TimeoutExpired(cmd="ffmpeg", timeout=120))):
                r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 504

    def test_ffmpeg_ausente_500(self, client, db, user, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id, storage_path=str(tmp_path / "source.mp4"))
        (tmp_path / "source.mp4").write_bytes(b"v")
        self._pushes_dueno(db, user, clip, job, video)
        with self._configurar(client, db, user):
            with patch("backend.api.routes.retrim.subprocess.run", Mock(side_effect=FileNotFoundError("ffmpeg"))):
                r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 500
        assert "no instalado" in r.json()["detail"]

    def test_sin_archivo_de_salida_500(self, client, db, user, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id, storage_path=str(tmp_path / "source.mp4"))
        (tmp_path / "source.mp4").write_bytes(b"v")
        self._pushes_dueno(db, user, clip, job, video)
        ok = SimpleNamespace(returncode=0, stderr=b"")
        with self._configurar(client, db, user):
            with patch("backend.api.routes.retrim.subprocess.run", Mock(return_value=ok)):
                r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 0.0, "end_time": 20.0})
        assert r.status_code == 500
        assert "no produjo archivo" in r.json()["detail"]

    def test_retrim_exitoso(self, client, db, user, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id, storage_path=str(tmp_path / "source.mp4"))
        (tmp_path / "source.mp4").write_bytes(b"v")
        self._pushes_dueno(db, user, clip, job, video)

        def _ffmpeg_falso(cmd: list[str], **kwargs: Any) -> Any:
            out_path = cmd[-1]
            (out_path[:1] if False else __import__("pathlib").Path(out_path)).write_bytes(b"retrim")
            return SimpleNamespace(returncode=0, stderr=b"")

        with self._configurar(client, db, user):
            with patch("backend.api.routes.retrim.subprocess.run", Mock(side_effect=_ffmpeg_falso)):
                r = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 5.0, "end_time": 35.0})
        assert r.status_code == 200
        data = r.json()
        assert data["start_time"] == 5.0
        assert data["duration"] == 30.0
        assert data["status"] == "ready"
        assert clip.storage_path.endswith(".mp4")


# ------------------------------------------------------------------- stream


class TestStreamJobs:
    @contextlib.contextmanager
    def _configurar(self, client, db: FakeSession, user: Any) -> Any:
        from backend_fastapi.app.deps import get_current_user, get_db
        from backend_fastapi.app.main import app

        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        # stream.py importa SessionLocal desde database en cada iteración
        with patch("backend_fastapi.app.database.SessionLocal", lambda: db):
            try:
                yield client
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    def test_stream_completa_con_done(self, client, db, user) -> None:
        video = make_video(user.id)
        job = make_job(video.id, status="completed")
        db.push_result(FakeResult(scalar=job))
        db.push_result(FakeResult(scalar=video))
        with self._configurar(client, db, user):
            r = client.get(f"/jobs/{job.id}/stream")
        assert r.status_code == 200
        assert '"status": "completed"' in r.text.replace("COMPLETED", "completed").replace('"status": "completed"', '"status": "completed"') or "completed" in r.text
        assert "event: done" in r.text

    def test_job_inexistente(self, client, db, user) -> None:
        db.push_result(FakeResult(scalar=None))
        with self._configurar(client, db, user):
            r = client.get(f"/jobs/{uuid_lib.uuid4()}/stream")
        assert "Job no encontrado" in r.text

    def test_job_de_otro_usuario(self, client, db, user) -> None:
        otro = make_usuario()
        video = make_video(otro.id)
        job = make_job(video.id)
        db.push_result(FakeResult(scalar=job))
        db.push_result(FakeResult(scalar=video))
        with self._configurar(client, db, user):
            r = client.get(f"/jobs/{job.id}/stream")
        assert "No autorizado" in r.text

    def test_job_id_invalido(self, client, db, user) -> None:
        with self._configurar(client, db, user):
            r = client.get("/jobs/no-es-uuid/stream")
        assert "event: error" in r.text
        assert "inv" in r.text  # job_id inválido (json.dumps con ensure_ascii)

    def test_to_event_mapeos(self) -> None:
        assert _to_event("pending").progress == 0
        assert _to_event("processing").progress == 55
        assert _to_event("PROCESSING").status == stream_mod.AutopilotJobStatus.scoring.value
        assert _to_event("completed").progress == 100
        assert _to_event("failed").status == stream_mod.AutopilotJobStatus.failed.value
        # status conocido por el enum pero no en el mapa
        intermedio = _to_event(stream_mod.AutopilotJobStatus.transcribing.value)
        assert intermedio.progress == 50
        # status completamente desconocido
        desconocido = _to_event("WEIRD")
        assert desconocido.progress == 0
        assert desconocido.status == "weird"


# ---------------------------------------------------------------------- CLI


class TestCliHelpers:
    def test_as_seconds(self) -> None:
        assert cli_mod._as_seconds(12) == 12.0
        assert cli_mod._as_seconds(1.5) == pytest.approx(1.5)
        assert cli_mod._as_seconds("12.5") == pytest.approx(12.5)
        assert cli_mod._as_seconds("00:01:05") == pytest.approx(65.0)
        assert cli_mod._as_seconds("2:30") == pytest.approx(150.0)
        with pytest.raises(ValueError, match="Timestamp inválido"):
            cli_mod._as_seconds("1:2:3:4")

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
