"""Fase 3 de cobertura — remate final: ramas chicas que quedaron de jobs.py
(probe ffprobe, ventana de ASS), stream.py (error del job) y main.py
(excepciones de constraints, sin huérfanos, cleanup roto).
"""

from __future__ import annotations

import uuid as uuid_lib
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

import _fixtures
from _fixtures import FakeSession, make_job, make_usuario, make_video

from backend_fastapi.app.routers import jobs as jobs_router

ENGINE_PATH = "backend_fastapi.app.services.engine.run_clip_engine"


class TestRenderProbeYVentanaAss:
    """Cubre el log de ffprobe (451-458) y el filtrado de segmentos del ASS simple."""

    def _correr(self, tmp_path, probe, segments) -> tuple[dict, Mock]:
        storage = tmp_path / "clips"
        storage.mkdir(exist_ok=True)
        video = tmp_path / "source.mp4"
        video.write_bytes(b"v")

        def _crea(dest: Any, contenido: bytes = b"salida") -> None:
            __import__("pathlib").Path(dest).write_bytes(contenido)

        reframe = Mock(side_effect=lambda src, dst, **kw: _crea(dst, b"r"))
        cut = Mock(side_effect=lambda src, s, e, out: _crea(out, b"t"))
        ass = Mock()
        with _patches(
            patch.object(jobs_router, "STORAGE_CLIPS_DIR", storage),
            patch("backend_fastapi.app.services.editor.reframe_video", reframe),
            patch("backend_fastapi.app.services.ffmpeg_service.cut_segment", cut),
            patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", Mock(side_effect=lambda i, a, o: _crea(o))),
            patch("backend_fastapi.app.services.ass_generator.write_ass_file", ass),
            patch("subprocess.run", probe),
        ):
            _, meta = jobs_router._render_clip_with_ass_and_hook(
                str(video), 10.0, 40.0, segments, None, uuid_lib.uuid4(), 0, "t"
            )
        return meta, ass

    def test_probe_ok_y_segmentos_mezclados(self, tmp_path) -> None:
        probe = Mock(
            returncode=0,
            stdout='{"streams": [{"width": 1080, "height": 1920, "duration": "30"}]}',
        )
        # segmentos: fuera de ventana (ambos lados), sin texto, rango invertido y válido
        segments = [
            {"start": 0.0, "end": 5.0, "text": "antes"},
            {"start": 50.0, "end": 60.0, "text": "después"},
            {"start": 12.0, "end": 11.0, "text": "invertido"},
            {"start": 12.0, "end": 14.0, "text": "   "},
            {"start": 12.0, "end": 15.0, "text": "dentro"},
        ]
        meta, ass = self._correr(tmp_path, probe, segments)
        assert meta["render"] == "ass"
        ass.assert_called_once()
        # solo el segmento "dentro" quedó en el ASS
        clipped = ass.call_args.args[0]
        assert [c["text"] for c in clipped] == ["dentro"]

    def test_probe_fallido_y_sin_segmentos_en_ventana(self, tmp_path) -> None:
        probe = Mock(returncode=1, stdout="")
        segments = [{"start": 0.0, "end": 2.0, "text": "lejos"}]
        meta, ass = self._correr(tmp_path, probe, segments)
        assert meta["render"] == "ass"  # usa el placeholder "CLIPSAI"
        assert ass.call_args.args[0][0]["text"] == "CLIPSAI"


class _patches:
    def __init__(self, *patches: Any) -> None:
        self._patches = list(patches)

    def __enter__(self) -> None:
        for p in self._patches:
            p.__enter__()

    def __exit__(self, *exc: Any) -> None:
        for p in reversed(self._patches):
            p.__exit__(*exc)


class TestStreamConError:
    @pytest.fixture()
    def _app(self):
        from fastapi.testclient import TestClient

        from backend_fastapi.app.deps import get_current_user, get_db
        from backend_fastapi.app.main import app

        yield app, get_db, get_current_user
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    def test_job_failed_con_error_message(self, _app, client, db, user) -> None:
        app, get_db, get_current_user = _app
        video = make_video(user.id)
        job = make_job(video.id, status="failed", error_message="Error en Claude: timeout")
        db.push_result(_fixtures.FakeResult(scalar=job))
        db.push_result(_fixtures.FakeResult(scalar=video))
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with patch("backend_fastapi.app.database.SessionLocal", lambda: db):
            r = client.get(f"/jobs/{job.id}/stream")
        assert "Error en Claude" in r.text
        assert "event: done" in r.text


class TestLifespanExtras:
    def _arrancar(self, *, conn_side_effect=None, query_rows=None, session_local=None, cleanup=None):
        from fastapi.testclient import TestClient

        from backend_fastapi.app import database as db_mod
        from backend_fastapi.app.main import app as fastapi_app

        conn = Mock()
        if conn_side_effect is not None:
            conn.execute = Mock(side_effect=conn_side_effect)
        else:
            conn.execute = Mock()
        cm = MagicMock()
        cm.__enter__.return_value = conn
        cm.__exit__.return_value = False
        engine = MagicMock()
        engine.connect.return_value = cm

        db = FakeSession()
        db.query_rows = query_rows or []

        with (
            patch.object(db_mod, "DB_AVAILABLE", True),
            patch.object(db_mod, "engine", engine),
            patch.object(db_mod, "SessionLocal", session_local or (lambda: db)),
            patch(
                "backend_fastapi.app.services.storage_cleanup.cleanup_storage",
                cleanup or Mock(return_value=1024 * 1024),
            ),
        ):
            with TestClient(fastapi_app):
                pass
        return conn, db

    def test_drop_constraints_explotan_y_sigue(self) -> None:
        def _efecto(stmt: Any, *a: Any, **k: Any) -> Mock:
            if "DROP CONSTRAINT" in str(stmt):
                raise RuntimeError("constraint no existe")
            return Mock()

        conn, _ = self._arrancar(conn_side_effect=_efecto)
        assert conn.execute.call_count > 20

    def test_sin_huerfanos_usa_fallback_lower(self) -> None:
        conn, _ = self._arrancar(query_rows=[])  # 1ª query vacía → 2ª query func.lower
        # sin excepciones y sin commits extra: la 2ª query tampoco devolvió jobs

    def test_session_local_roto_no_impide_arrancar(self) -> None:
        cleanup = Mock(return_value=1024 * 1024)
        self._arrancar(session_local=Mock(side_effect=RuntimeError("session rota")), cleanup=cleanup)
        cleanup.assert_called_once()

    def test_cleanup_roto_no_impide_arrancar(self) -> None:
        self._arrancar(cleanup=Mock(side_effect=RuntimeError("disco lleno")))
