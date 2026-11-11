"""Fase 3 de cobertura — brechas chicas: `database.py` (normalización de URL y
`get_db`), `deps.py` (tokens inválidos/usuario inexistente) y
`routers/_clip_common.py`.
"""

from __future__ import annotations

import uuid as uuid_lib
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

import _fixtures
from _fixtures import FakeResult, FakeSession, make_clip, make_job, make_usuario, make_video

from backend_fastapi.app import database as db_mod
from backend_fastapi.app.database import _fallback_db_url, get_db
from backend_fastapi.app.deps import get_current_user
from backend_fastapi.app.routers import _clip_common
from backend_fastapi.app.security import create_access_token


class TestFallbackDbUrl:
    def test_esquema_postgres(self) -> None:
        assert _fallback_db_url("postgres://u:p@db:5432/clipsai").startswith("postgresql+psycopg2://")

    def test_esquema_postgresql(self) -> None:
        url = _fallback_db_url("postgresql://u:p@host:5432/clipsai")
        assert url.startswith("postgresql+psycopg2://")

    def test_docker_con_host_local(self, monkeypatch) -> None:
        monkeypatch.setattr(db_mod, "_is_docker", lambda: True)
        url = _fallback_db_url("postgresql://u:p@127.0.0.1:5432/clipsai")
        assert "@db:" in url

    def test_fuera_de_docker_con_db_resolvible(self, monkeypatch) -> None:
        monkeypatch.setattr(db_mod, "_is_docker", lambda: False)
        with patch("socket.getaddrinfo", Mock()):
            url = _fallback_db_url("postgresql://u:p@db:5432/clipsai")
        assert url == "postgresql+psycopg2://u:p@db:5432/clipsai"  # esquema normalizado, host intacto

    def test_fuera_de_docker_con_db_no_resolvible(self, monkeypatch) -> None:
        monkeypatch.setattr(db_mod, "_is_docker", lambda: False)
        with patch("socket.getaddrinfo", Mock(side_effect=OSError("no resuelve"))):
            url = _fallback_db_url("postgresql://u:p@db:5432/clipsai")
        assert "@127.0.0.1:" in url

    def test_is_docker_con_excepcion(self, monkeypatch) -> None:
        with patch("pathlib.Path.exists", Mock(side_effect=OSError("no"))):
            assert db_mod._is_docker() is False


class TestGetDbDependencia:
    def test_sin_db_lanza_runtime_error(self, monkeypatch) -> None:
        monkeypatch.setattr(db_mod, "DB_AVAILABLE", False)
        gen = get_db()
        with pytest.raises(RuntimeError, match="Database not available"):
            next(gen)

    def test_entrega_sesion_y_cierra(self, monkeypatch) -> None:
        session = Mock()
        monkeypatch.setattr(db_mod, "DB_AVAILABLE", True)
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: session)
        gen = get_db()
        assert next(gen) is session
        gen.close()  # ejecuta el finally del generador
        session.close.assert_called_once()


class TestGetCurrentUserBrechas:
    def _bearer(self, token: str) -> Any:
        return SimpleNamespace(credentials=token)

    def test_token_con_sub_invalido(self) -> None:
        db = FakeSession()
        token = create_access_token(subject="no-es-uuid")
        with pytest.raises(HTTPException, match="401"):
            get_current_user(self._bearer(token), db)

    def test_usuario_inexistente(self, db) -> None:
        token = create_access_token(subject=str(uuid_lib.uuid4()))
        db.push_result(FakeResult(scalar=None))
        with pytest.raises(HTTPException, match="Usuario no encontrado"):
            get_current_user(self._bearer(token), db)


class TestClipCommon:
    def test_get_clip_or_404(self, db) -> None:
        clip = make_clip(uuid_lib.uuid4())
        db.seed(clip)
        assert _clip_common.get_clip_or_404(db, clip.id) is clip
        with pytest.raises(HTTPException, match="404"):
            _clip_common.get_clip_or_404(db, uuid_lib.uuid4())

    def test_resolve_via_job(self, db) -> None:
        video = make_video(uuid_lib.uuid4())
        job = make_job(video.id)
        clip = make_clip(job.id, video_id=None)
        db.seed(video, job, clip)
        assert _clip_common.resolve_clip_video(db, clip) is video

    def test_resolve_sin_nada(self, db) -> None:
        clip = make_clip(uuid_lib.uuid4(), video_id=None)
        clip.job_id = None
        assert _clip_common.resolve_clip_video(db, clip) is None

    def test_ownership(self, db, user) -> None:
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id)
        db.seed(video, job, clip)
        _clip_common.assert_clip_ownership(db, clip, user)  # ok

        otro = make_usuario()
        video_otro = make_video(otro.id)
        job_otro = make_job(video_otro.id)
        clip_otro = make_clip(job_otro.id, video_otro.id)
        db.seed(video_otro, job_otro, clip_otro)
        with pytest.raises(HTTPException, match="403"):
            _clip_common.assert_clip_ownership(db, clip_otro, user)

        clip_huerfano = make_clip(uuid_lib.uuid4(), video_id=None)
        clip_huerfano.job_id = None
        with pytest.raises(HTTPException, match="404"):
            _clip_common.assert_clip_ownership(db, clip_huerfano, user)
