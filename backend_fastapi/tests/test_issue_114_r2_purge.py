"""Tests para la Issue #114: purga R2 en DELETE clip, lifecycle 24h y disconnect OAuth.

Todas las llamadas a R2 están mockeadas con un FakeS3Client; la DB es FakeSession.
"""

from __future__ import annotations

import uuid as uuid_lib
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
from _fixtures import FakeResult, FakeSession, make_clip, make_job, make_usuario, make_video
import conftest as _c

from backend_fastapi.app.services import r2_service as rs
from backend_fastapi.app.services.r2_service import (
    apply_lifecycle_rule_24h,
    BUCKET_NAME_ENV,
    delete_r2_object,
    get_r2_client,
    r2_object_key_from_url,
)

make_social_account = _c.make_social_account


# ------------------------------------------------------------------ Fake S3


class FakeS3Client:
    """Cliente S3/R2 falso que registra llamadas y permite inyectar fallos."""

    def __init__(self, should_fail: bool = False) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.lifecycle_calls: int = 0
        self.should_fail = should_fail

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N802
        self.deleted.append((Bucket, Key))
        if self.should_fail:
            raise RuntimeError("R2 delete falló")

    def put_bucket_lifecycle_configuration(self, **kwargs: Any) -> None:  # noqa: N802
        self.lifecycle_calls += 1


# ------------------------------------------------------------------ r2_object_key_from_url


class TestR2ObjectKeyFromUrl:
    def test_extrae_key_de_url_publica_r2(self) -> None:
        url = "https://videos.clipsai.xyz/clips/vid-abc/1_vertical.mp4"
        key = r2_object_key_from_url(url, public_url="https://videos.clipsai.xyz")
        assert key == "clips/vid-abc/1_vertical.mp4"

    def test_extrae_key_de_url_publica_sin_esquema(self) -> None:
        url = "https://videos.clipsai.xyz/uploads/abc.mp4"
        key = r2_object_key_from_url(url, public_url="videos.clipsai.xyz")
        assert key == "uploads/abc.mp4"

    def test_rechaza_url_de_otro_dominio(self) -> None:
        url = "https://otro.dominio.com/uploads/abc.mp4"
        assert r2_object_key_from_url(url, public_url="https://videos.clipsai.xyz") is None

    def test_rechaza_path_traversal(self) -> None:
        url = "https://videos.clipsai.xyz/uploads/../../etc/passwd"
        assert r2_object_key_from_url(url, public_url="https://videos.clipsai.xyz") is None

    def test_ruta_local_retorna_none(self) -> None:
        assert r2_object_key_from_url("/storage/clips/clip.mp4") is None
        assert r2_object_key_from_url("") is None

    def test_acepta_key_directa_con_prefijo_valido(self) -> None:
        assert r2_object_key_from_url("uploads/abc.mp4") == "uploads/abc.mp4"
        assert r2_object_key_from_url("clips/vid/1_vertical.mp4") == "clips/vid/1_vertical.mp4"
        assert r2_object_key_from_url("runpod-inputs/xyz.mp4") == "runpod-inputs/xyz.mp4"

    def test_rechaza_key_directa_con_travesia(self) -> None:
        assert r2_object_key_from_url("uploads/../../etc/passwd") is None

    def test_rechaza_key_directa_sin_prefijo_valido(self) -> None:
        assert r2_object_key_from_url("otros/archivo.mp4") is None


# ------------------------------------------------------------------ delete_r2_object


class TestDeleteR2Object:
    def test_elimina_objeto_y_registra(self) -> None:
        s3 = FakeS3Client()
        assert delete_r2_object(s3, "bucket", "clips/x.mp4") is True
        assert s3.deleted == [("bucket", "clips/x.mp4")]

    def test_best_effort_no_lanza_si_falla(self) -> None:
        s3 = FakeS3Client(should_fail=True)
        # Nunca lanza, retorna True aunque falle (best-effort)
        assert delete_r2_object(s3, "bucket", "clips/x.mp4") is True
        assert s3.deleted == [("bucket", "clips/x.mp4")]


# ------------------------------------------------------------------ apply_lifecycle_rule_24h


class TestApplyLifecycleRule24h:
    def test_aplica_regla_24h(self) -> None:
        s3 = FakeS3Client()
        assert apply_lifecycle_rule_24h(s3, "bucket") is True
        assert s3.lifecycle_calls == 1

    def test_idempotente_dos_llamadas(self) -> None:
        s3 = FakeS3Client()
        assert apply_lifecycle_rule_24h(s3, "bucket") is True
        assert apply_lifecycle_rule_24h(s3, "bucket") is True
        assert s3.lifecycle_calls == 2


# ------------------------------------------------------------------ get_r2_client (sin credenciales reales)


class TestGetR2Client:
    def test_sin_credenciales_lanza_runtimeerror(self, monkeypatch) -> None:
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        with pytest.raises(RuntimeError, match="Faltan"):
            get_r2_client()


# ------------------------------------------------------------------ DELETE /clips/{id} purga R2


def _setup_app_with_clip(db: FakeSession, storage_path: str, user_id: Any) -> Any:
    """Crea un clip con storage_path dado y retorna el TestClient."""
    from backend_fastapi.app.main import app
    from backend_fastapi.app.deps import get_current_user, get_db
    from fastapi.testclient import TestClient

    video = make_video(user_id)
    job = make_job(video.id)
    clip = make_clip(job.id, video.id, storage_path=storage_path)
    db.seed(video, job, clip)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: make_usuario(id=user_id)
    return TestClient(app), clip


class TestDeleteClipR2Purge:
    def test_delete_clip_r2_purge_objeto_y_fila(self, monkeypatch) -> None:
        user_id = uuid_lib.uuid4()
        db = FakeSession()
        s3 = FakeS3Client()

        def fake_get_r2_client():
            return s3

        with patch("backend_fastapi.app.routers.clips.get_r2_client", fake_get_r2_client), \
             patch("backend_fastapi.app.routers.clips.BUCKET_NAME_ENV", "clipsai-videos"):
            client, clip = _setup_app_with_clip(
                db, "https://videos.clipsai.xyz/clips/vid-abc/1_vertical.mp4", user_id
            )
            resp = client.delete(f"/clips/{clip.id}")
            assert resp.status_code == 204
            assert s3.deleted == [("clipsai-videos", "clips/vid-abc/1_vertical.mp4")]
            # La fila se borró: FakeSession registra el delete
            assert clip in db.deleted

    def test_delete_clip_r2_best_effort_quando_s3_falla(self, monkeypatch) -> None:
        user_id = uuid_lib.uuid4()
        db = FakeSession()
        s3 = FakeS3Client(should_fail=True)

        def fake_get_r2_client():
            return s3

        with patch("backend_fastapi.app.routers.clips.get_r2_client", fake_get_r2_client), \
             patch("backend_fastapi.app.routers.clips.BUCKET_NAME_ENV", "clipsai-videos"):
            client, clip = _setup_app_with_clip(
                db, "https://videos.clipsai.xyz/clips/vid-abc/1_vertical.mp4", user_id
            )
            resp = client.delete(f"/clips/{clip.id}")
            # Aunque R2 falle, DB debe borrar la fila (204)
            assert resp.status_code == 204
            # La fila se borró: FakeSession registra el delete
            assert clip in db.deleted

    def test_delete_clip_r2_no_extrae_key_retorna_204(self, monkeypatch) -> None:
        user_id = uuid_lib.uuid4()
        db = FakeSession()
        s3 = FakeS3Client()

        def fake_get_r2_client():
            return s3

        # URL R2 sin prefijo válido -> no se intenta delete_object
        with patch("backend_fastapi.app.routers.clips.get_r2_client", fake_get_r2_client), \
             patch("backend_fastapi.app.routers.clips.BUCKET_NAME_ENV", "clipsai-videos"):
            client, clip = _setup_app_with_clip(
                db, "https://videos.clipsai.xyz/otros/archivo.mp4", user_id
            )
            resp = client.delete(f"/clips/{clip.id}")
            assert resp.status_code == 204
            assert s3.deleted == []

    def test_delete_clip_r2_fallo_cliente_no_bloquea_db(self, monkeypatch) -> None:
        user_id = uuid_lib.uuid4()
        db = FakeSession()

        def fake_get_r2_client():
            raise RuntimeError("no hay credenciales")

        with patch("backend_fastapi.app.routers.clips.get_r2_client", fake_get_r2_client):
            client, clip = _setup_app_with_clip(
                db, "https://videos.clipsai.xyz/clips/vid-abc/1_vertical.mp4", user_id
            )
            resp = client.delete(f"/clips/{clip.id}")
            assert resp.status_code == 204
            # La fila se borró: FakeSession registra el delete
            assert clip in db.deleted

    def test_delete_clip_local_todavía_unlink(self, monkeypatch) -> None:
        user_id = uuid_lib.uuid4()
        db = FakeSession()
        s3 = FakeS3Client()

        unlink_calls: list[str] = []

        class FakePath:
            def __init__(self, p: str):
                self.p = p

            def is_file(self) -> bool:
                return True

            def unlink(self) -> None:
                unlink_calls.append(self.p)

        def fake_get_r2_client():
            return s3

        with patch("backend_fastapi.app.routers.clips.get_r2_client", fake_get_r2_client), \
             patch("backend_fastapi.app.routers.clips.BUCKET_NAME_ENV", "clipsai-videos"), \
             patch("backend_fastapi.app.routers.clips.Path", FakePath):
            client, clip = _setup_app_with_clip(
                db, "/storage/clips/clip_local.mp4", user_id
            )
            resp = client.delete(f"/clips/{clip.id}")
            assert resp.status_code == 204
            assert unlink_calls == ["/storage/clips/clip_local.mp4"]
            assert s3.deleted == []
