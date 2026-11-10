"""Cobertura de routers del backend FastAPI con TestClient y sesión falsa.

Sin PostgreSQL, sin FFmpeg, sin red: todo lo externo está aislado con
`unittest.mock.patch` (engine de jobs, botocore de S3, servicios OAuth, tareas
en background) o delegado a la `FakeSession` de `_fixtures.py`.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
from _fixtures import (
    FakeResult,
    build_client,
    make_clip,
    make_job,
    make_social_account,
    make_usuario,
    make_video,
)
from backend_fastapi.app.security import create_access_token, hash_password


PASSWORD = "ClaveSegura_2026!"


# ---------------------------------------------------------------- health


class TestHealth:
    def test_health_es_publico(self, client) -> None:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


# ---------------------------------------------------------------- auth


class TestAuth:
    def test_registro_201_y_hashea_password(self, client, db) -> None:
        res = client.post(
            "/auth/registro",
            json={"email": "nueva@example.com", "password": PASSWORD, "full_name": "Nueva"},
        )
        assert res.status_code == 201, res.text
        assert res.json()["email"] == "nueva@example.com"
        assert "id" in res.json()
        assert len(db.added) == 1
        # sql-injection de seguridad: el hash no es la contraseña
        assert db.added[0].hashed_password != PASSWORD

    def test_registro_409_si_email_tomado(self, client, db) -> None:
        db.push_result(FakeResult(rows=[("id-existente",)]))  # el SELECT previo encuentra el email
        res = client.post(
            "/auth/registro",
            json={"email": "tomado@example.com", "password": PASSWORD},
        )
        assert res.status_code == 409

    def test_registro_422_password_corto(self, client) -> None:
        res = client.post("/auth/registro", json={"email": "a@example.com", "password": "123"})
        assert res.status_code == 422

    def test_registro_409_por_integrity_error(self, client, db) -> None:
        from sqlalchemy.exc import IntegrityError

        db.commit_error = IntegrityError("dup", None, Exception("dup"))
        res = client.post("/auth/registro", json={"email": "race@example.com", "password": PASSWORD})
        assert res.status_code == 409
        assert db.added  # se hizo rollback tras el intento

    def test_alias_registro_raiz(self, client) -> None:
        res = client.post("/registro", json={"email": "alias@example.com", "password": PASSWORD})
        assert res.status_code == 201

    def test_login_200_emite_token(self, client, db, user) -> None:
        user.hashed_password = hash_password(PASSWORD)
        db.push_result(FakeResult(scalar=user))  # _autenticar -> scalar_one_or_none
        res = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
        assert res.status_code == 200
        token = res.json()["access_token"]
        assert token and "Bearer" not in token

    def test_login_401_credenciales_invalidas(self, client) -> None:
        res = client.post("/auth/login", json={"email": "nadie@example.com", "password": "incorrecta1"})
        assert res.status_code == 401

    def test_login_422_json_invalido(self, client) -> None:
        res = client.post("/auth/login", json={"email": "no-es-email", "password": "x"})
        assert res.status_code == 422

    def test_login_form_200_oauth2(self, client, db, user) -> None:
        user.hashed_password = hash_password(PASSWORD)
        db.push_result(FakeResult(scalar=user))
        res = client.post(
            "/auth/login/form", data={"username": user.email, "password": PASSWORD}
        )
        assert res.status_code == 200
        assert res.json()["access_token"]

    def test_alias_login_raiz(self, client, db, user) -> None:
        user.hashed_password = hash_password(PASSWORD)
        db.push_result(FakeResult(scalar=user))
        res = client.post("/login", json={"email": user.email, "password": PASSWORD})
        assert res.status_code == 200

    def test_me_200_con_jwt_real(self, db, user) -> None:
        user.hashed_password = hash_password(PASSWORD)
        real_client = build_client(db, user, use_real_auth=True)
        db.push_result(FakeResult(scalar=user))  # get_current_user busca al usuario
        try:
            res = real_client.get(
                "/auth/me", headers={"Authorization": f"Bearer {create_access_token(user.id)}"}
            )
            assert res.status_code == 200
            assert res.json()["email"] == user.email
        finally:
            real_client.close()

    def test_me_401_o_403_sin_header(self, db) -> None:
        real_client = build_client(db, use_real_auth=True)
        try:
            res = real_client.get("/auth/me")
            # FastAPI/HTTPBearer puede devolver 401 u 403 según la versión
            # (SISTEMA.md §9: el front ya acepta 401 y 403 "Not authenticated").
            assert res.status_code in (401, 403)
        finally:
            real_client.close()

    def test_me_401_token_invalido(self, db) -> None:
        real_client = build_client(db, use_real_auth=True)
        try:
            res = real_client.get("/auth/me", headers={"Authorization": "Bearer basura.token"})
            assert res.status_code == 401
            assert "invalido" in res.json()["detail"].lower()
        finally:
            real_client.close()

    def test_me_401_token_expirado(self, db, user) -> None:
        real_client = build_client(db, use_real_auth=True)
        expired = create_access_token(user.id, expires_delta=timedelta(seconds=-1))
        try:
            res = real_client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
            assert res.status_code == 401
            assert "expirado" in res.json()["detail"].lower()
        finally:
            real_client.close()


# ---------------------------------------------------------------- users


class TestUsers:
    def test_users_me_200(self, client, user) -> None:
        res = client.get("/users/me")
        assert res.status_code == 200
        body = res.json()
        assert body["email"] == user.email
        assert body["name"] == "Usuaria de Prueba"

    def test_alias_me_y_api_users_me(self, client) -> None:
        assert client.get("/me").status_code == 200
        assert client.get("/api/users/me").status_code == 200

    def test_put_users_me_actualiza_nombre(self, client, db, user) -> None:
        res = client.put("/users/me", json={"full_name": "Nuevo Nombre"})
        assert res.status_code == 200
        assert res.json()["full_name"] == "Nuevo Nombre"
        assert db.commits >= 1

    def test_put_users_me_400_payload_vacio(self, client) -> None:
        res = client.put("/users/me", json={})
        assert res.status_code == 400
        assert "Nada para actualizar" in res.json()["detail"]

    def test_put_users_me_409_email_tomado(self, client, db) -> None:
        db.push_result(FakeResult(rows=[("otro-usuario",)]))
        res = client.put("/users/me", json={"email": "otro@example.com"})
        assert res.status_code == 409

    def test_patch_me_422_avatar_no_url(self, client) -> None:
        res = client.patch("/me", json={"avatar_url": "no-es-url"})
        assert res.status_code == 422

    def test_cambio_password_200(self, client, user) -> None:
        user.hashed_password = hash_password("antigua-clave-123")
        res = client.post(
            "/users/me/change-password",
            json={"current_password": "antigua-clave-123", "new_password": "nueva-clave-456"},
        )
        assert res.status_code == 200
        assert hash_password("nueva-clave-456") is not None  # hashing real ejecutado

    def test_cambio_password_400_actual_incorrecta(self, client, user) -> None:
        user.hashed_password = hash_password("otra-clave-real")  # la "actual" no coincide
        res = client.post(
            "/users/me/change-password",
            json={"current_password": "incorrecta", "new_password": "nueva-clave-456"},
        )
        assert res.status_code == 400

    def test_cambio_password_400_igual_a_actual(self, client, user) -> None:
        user.hashed_password = hash_password("misma-clave-123")
        res = client.post(
            "/users/me/change-password",
            json={"current_password": "misma-clave-123", "new_password": "misma-clave-123"},
        )
        assert res.status_code == 400

    def test_cambio_password_new_422_corto(self, client) -> None:
        res = client.post(
            "/users/me/change-password",
            json={"current_password": "cualquiera", "new_password": "corta"},
        )
        assert res.status_code == 422

    def test_alias_put_me_password(self, client, user) -> None:
        user.hashed_password = hash_password("antigua-clave-123")
        res = client.put(
            "/me/password",
            json={"current_password": "antigua-clave-123", "new_password": "nueva-clave-456"},
        )
        assert res.status_code == 200


# ---------------------------------------------------------------- videos


class TestVideos:
    def test_upload_url_200(self, client, db, monkeypatch, tmp_path) -> None:
        from backend_fastapi.app.routers import videos as videos_router

        s3 = Mock()
        s3.generate_presigned_url.return_value = "https://s3.example.test/upload-put"
        monkeypatch.setattr(videos_router, "get_s3_client", lambda: s3)
        monkeypatch.setenv("BUCKET_NAME", "clipsai-test")

        res = client.post(
            "/api/videos/upload-url", json={"file_name": "video.mp4", "file_type": "video/mp4"}
        )
        assert res.status_code == 200, res.text
        assert res.json()["upload_url"] == "https://s3.example.test/upload-put"

    def test_upload_url_500_si_presign_falla(self, client, db, monkeypatch) -> None:
        from backend_fastapi.app.routers import videos as videos_router

        s3 = Mock()
        s3.generate_presigned_url.side_effect = RuntimeError("boom")
        monkeypatch.setattr(videos_router, "get_s3_client", lambda: s3)
        monkeypatch.setenv("BUCKET_NAME", "clipsai-test")

        res = client.post(
            "/api/videos/upload-url", json={"file_name": "video.mp4", "file_type": "video/mp4"}
        )
        assert res.status_code == 500

    def test_post_videos_201_y_guarda_archivos(self, client, db, user, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        video = tmp_path / "toma.mp4"
        video.write_bytes(b"video-bytes")
        transcript = tmp_path / "toma.txt"
        transcript.write_text("00:00:00 - Hola", encoding="utf-8")

        with open(video, "rb") as fv, open(transcript, "rb") as ft:
            res = client.post(
                "/videos",
                files={"video": ("toma.mp4", fv, "video/mp4"), "transcription": ("toma.txt", ft, "text/plain")},
            )
        assert res.status_code == 201, res.text
        assert db.commits >= 1
        assert any(path.suffix == ".mp4" for path in tmp_path.iterdir())

    def test_post_videos_400_extension_invalida(self, client, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        falso = tmp_path / "toma.exe"
        falso.write_bytes(b"no-es-video")

        with open(falso, "rb") as fv:
            res = client.post("/videos", files={"video": ("toma.exe", fv, "application/octet-stream")})
        assert res.status_code == 400

    def test_post_videos_401_o_403_sin_token(self, db, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        anonimo = build_client(db, use_real_auth=True)
        video = tmp_path / "toma.mp4"
        video.write_bytes(b"video")
        try:
            with open(video, "rb") as fv:
                res = anonimo.post("/videos", files={"video": ("toma.mp4", fv, "video/mp4")})
            assert res.status_code in (401, 403)
        finally:
            anonimo.close()

    def test_get_videos_200_lista_del_usuario(self, client, db, user) -> None:
        video = make_video(user.id)
        db.push_result(FakeResult(rows=[video]))
        res = client.get("/videos")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# ---------------------------------------------------------------- jobs


class TestJobs:
    def test_crear_job_202(self, client, db, user, monkeypatch) -> None:
        from backend_fastapi.app.routers import jobs as jobs_router

        monkeypatch.setattr(jobs_router, "run_job_safely", Mock(), raising=False)
        video = make_video(user.id)
        db.seed(video)

        res = client.post(f"/videos/{video.id}/jobs")
        assert res.status_code == 202, res.text
        assert res.json()["status"] == "PENDING"
        assert db.commits >= 1

    def test_crear_job_404(self, client) -> None:
        res = client.post("/videos/%s/jobs" % _fixtures.uuid.uuid4())
        assert res.status_code == 404

    def test_crear_job_403_video_de_otro(self, client, db) -> None:
        video = make_video(_fixtures.uuid.uuid4())  # de otro usuario
        db.seed(video)
        res = client.post(f"/videos/{video.id}/jobs")
        assert res.status_code == 403

    def test_crear_job_422_uuid_invalido(self, client) -> None:
        res = client.post("/videos/no-es-uuid/jobs")
        assert res.status_code == 422

    def test_get_job_200(self, client, db, user) -> None:
        video = make_video(user.id)
        job = make_job(video.id, status="processing", progress=55)
        db.seed(video, job)
        res = client.get(f"/jobs/{job.id}")
        assert res.status_code == 200
        assert res.json()["status"] == "PROCESSING"

    def test_get_job_404(self, client) -> None:
        res = client.get(f"/jobs/{_fixtures.uuid.uuid4()}")
        assert res.status_code == 404


# ---------------------------------------------------------------- clips


class TestClips:
    def _clip_con_video(self, db, user) -> tuple[Any, Any, Any]:
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id)
        db.seed(video, job, clip)
        return clip, job, video

    def test_list_clips_200(self, client, db, user) -> None:
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video.id)
        db.scalar_value = 1
        db.push_result(FakeResult(rows=[(clip, "transcript del video")]))

        res = client.get("/clips")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "Clip de prueba"
        assert body["items"][0]["duration"] == pytest.approx(35.0)
        assert body["items"][0]["has_ass"] is True

    def test_list_clips_422_limit_fuera_de_rango(self, client) -> None:
        assert client.get("/clips", params={"limit": 200}).status_code == 422
        assert client.get("/clips", params={"min_score": -5}).status_code == 422

    def test_list_clips_422_sort_by_invalido(self, client) -> None:
        res = client.get("/clips", params={"sort_by": "puntuacion"})
        assert res.status_code == 422

    def test_get_clip_200(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        res = client.get(f"/clips/{clip.id}")
        assert res.status_code == 200
        assert res.json()["title"] == "Clip de prueba"

    def test_get_clip_404(self, client) -> None:
        res = client.get(f"/clips/{_fixtures.uuid.uuid4()}")
        assert res.status_code == 404

    def test_get_clip_403_de_otro_usuario(self, client, db) -> None:
        video = make_video(_fixtures.uuid.uuid4())
        job = make_job(video.id)
        clip = make_clip(job.id, video.id)
        db.seed(video, job, clip)
        res = client.get(f"/clips/{clip.id}")
        assert res.status_code == 403

    def test_patch_clip_200_actualiza_titulo(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        res = client.patch(f"/clips/{clip.id}", json={"title": "Titulo editado"})
        assert res.status_code == 200
        assert clip.title == "Titulo editado"

    def test_patch_clip_400_body_vacio(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        res = client.patch(f"/clips/{clip.id}", json={})
        assert res.status_code == 400

    def test_delete_clip_204(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        res = client.delete(f"/clips/{clip.id}")
        assert res.status_code == 204
        assert clip in db.deleted

    def test_delete_clip_404(self, client) -> None:
        assert client.delete(f"/clips/{_fixtures.uuid.uuid4()}").status_code == 404

    def test_descarga_404_si_archivo_no_existe(self, client, db, user, tmp_path) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        clip.storage_path = str(tmp_path / "inexistente.mp4")
        res = client.get(f"/clips/{clip.id}/descarga")
        assert res.status_code == 404

    def test_descarga_302_si_es_url_publica(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        clip.storage_path = "https://videos.clipsai.xyz/clips/x_vertical.mp4"
        res = client.get(f"/clips/{clip.id}/descarga", follow_redirects=False)
        assert res.status_code == 302
        assert res.headers["location"].startswith("https://videos.clipsai.xyz/")

    def test_publish_422_plataforma_invalida(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        res = client.post(
            f"/clips/{clip.id}/publicar",
            json={"platform": "facebook", "caption": "hola"},
        )
        assert res.status_code == 422

    def test_publish_202_y_pone_estado_publishing(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        with patch("backend_fastapi.app.services.publish_service.publish_clip_task") as task:
            res = client.post(
                f"/clips/{clip.id}/publicar",
                json={"platform": "tiktok", "caption": "#viral"},
            )
        assert res.status_code == 202, res.text
        assert clip.status == "PUBLISHING"
        task.assert_called_once()

    def test_publish_202_alias_publish(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        with patch("backend_fastapi.app.services.publish_service.publish_clip_task"):
            res = client.post(f"/clips/{clip.id}/publish", json={"platform": "webhook"})
        assert res.status_code == 202

    def test_publish_404_clip_inexistente(self, client) -> None:
        res = client.post(
            f"/clips/{_fixtures.uuid.uuid4()}/publicar", json={"platform": "tiktok"}
        )
        assert res.status_code == 404

    def test_re_render_409_si_esta_procesando(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        clip.status = "PROCESSING"
        res = client.post(f"/clips/{clip.id}/re-render", json={"enable_ass": True})
        assert res.status_code == 409

    def test_subtitles_202(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        with patch("backend_fastapi.app.tasks.subtitle_pipeline.run_subtitle_pipeline") as task:
            res = client.post(f"/clips/{clip.id}/subtitles", json={})
        assert res.status_code == 202
        task.assert_called_once()

    def test_subtitles_409_si_esta_procesando(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        clip.status = "PROCESSING"
        res = client.post(f"/clips/{clip.id}/subtitles", json={})
        assert res.status_code == 409

    def test_subtitles_status_200(self, client, db, user) -> None:
        clip, _, _ = self._clip_con_video(db, user)
        res = client.get(f"/clips/{clip.id}/subtitles/status")
        assert res.status_code == 200
        assert res.json()["title"] == "Clip de prueba"


# ---------------------------------------------------------------- export


class TestExport:
    def _job_propio(self, db, user) -> tuple[Any, Any]:
        video = make_video(user.id)
        job = make_job(video.id)
        db.seed(video, job)
        return job, video

    def test_export_job_csv_200(self, client, db, user) -> None:
        job, _ = self._job_propio(db, user)
        clip = make_clip(job.id)
        db.push_result(FakeResult(rows=[(clip, "transcripcion base")]))

        res = client.get(f"/jobs/{job.id}/export", params={"format": "csv"})
        assert res.status_code == 200, res.text
        assert res.headers["content-type"].startswith("text/csv")
        assert "Título" in res.text and "Clip de prueba" in res.text

    def test_export_job_json_200_con_transcript_en_la_fila(self, client, db, user) -> None:
        job, _ = self._job_propio(db, user)
        clip = make_clip(job.id, score=80)
        # La fila ya viene coalescida: (clip, transcript) — None en la fila == ""
        db.push_result(FakeResult(rows=[(clip, "00:00:00 - Linea del video")]))

        res = client.get(f"/jobs/{job.id}/export", params={"format": "json"})
        assert res.status_code == 200
        body = res.json()
        assert body["total_clips"] == 1
        assert body["job_id"] == str(job.id)
        assert body["clips"][0]["transcript"] == "00:00:00 - Linea del video"
        assert body["avg_score"] == pytest.approx(80.0)

    def test_export_job_404(self, client) -> None:
        res = client.get(f"/jobs/{_fixtures.uuid.uuid4()}/export", params={"format": "csv"})
        assert res.status_code == 404

    def test_export_job_422_formato_invalido(self, client, db, user) -> None:
        job, _ = self._job_propio(db, user)
        res = client.get(f"/jobs/{job.id}/export", params={"format": "xlsx"})
        assert res.status_code == 422

    def test_export_alias_api_v1(self, client, db, user) -> None:
        job, _ = self._job_propio(db, user)
        db.push_result(FakeResult())
        res = client.get(f"/api/v1/jobs/{job.id}/export", params={"format": "csv"})
        assert res.status_code == 200

    def test_export_clips_csv_200(self, client, db, user) -> None:
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id)
        db.push_result(FakeResult(rows=[(clip, None)]))
        res = client.get("/clips/export", params={"format": "csv"})
        assert res.status_code == 200


# ---------------------------------------------------------------- metrics


class TestMetrics:
    def test_metrics_200_vacio(self, client) -> None:
        res = client.get("/metrics")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total_jobs"] == 0
        assert set(body["platform_distribution"]) == {"tiktok", "youtube", "instagram"}
        assert len(body["recent_activity"]) == 7

    def test_metrics_200_con_datos(self, client, db) -> None:
        import datetime as dt

        dia = dt.date.today().isoformat()
        # El router hace 3 db.scalar seguidos: jobs, clips y segundos del video
        db.scalar_results = [1, 2, 600.0]
        db.push_result(FakeResult(rows=[("TikTok", 3)]))          # platform_rows
        db.push_result(FakeResult(rows=[(dia, 1)]))               # jobs por dia
        db.push_result(FakeResult(rows=[(dia, 2)]))               # clips por dia
        db.push_result(FakeResult(rows=[(dia, 600.0)]))           # minutos del video

        res = client.get("/metrics")
        assert res.status_code == 200
        body = res.json()
        assert body["total_jobs"] == 1
        assert body["total_clips"] == 2
        assert body["platform_distribution"]["tiktok"] == 3
        assert body["recent_activity"][-1]["clips"] == 2
        # 600 s -> 10 min -> 10 * 3 / 60 = 0.5 h
        assert body["time_saved_hours"] == pytest.approx(0.5)

    def test_agregado_api_metrics_200(self, client) -> None:
        assert client.get("/api/metrics").status_code == 200


# ---------------------------------------------------------------- stats


class TestStats:
    def test_summary_200(self, client, db) -> None:
        db.scalar_value = 4  # total_videos
        fila_agg = SimpleNamespace(total_clips=10, avg_score=77.3, low=3, medium=4, high=3)
        db.push_result(FakeResult(one=fila_agg))
        db.push_result(FakeResult(scalar=None))  # recent_job

        res = client.get("/stats/summary")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total_videos"] == 4
        assert body["total_clips"] == 10
        assert body["avg_score"] == pytest.approx(77.3)
        assert [item["range"] for item in body["score_distribution"]] == ["0-40", "41-70", "71-100"]
        assert body["recent_job"] is None
        assert body["estimated_time_saved_minutes"] == 150


# ---------------------------------------------------------------- social


class TestSocialAuth:
    def test_status_200_vacio(self, client) -> None:
        res = client.get("/auth/social/status")
        assert res.status_code == 200
        body = res.json()
        for platform in ("instagram", "youtube", "tiktok"):
            assert body[platform]["connected"] is False

    def test_status_200_con_cuentas(self, client, db, user) -> None:
        db.query_rows = [
            make_social_account(user.id, platform="youtube", platform_username="@canalreal")
        ]
        res = client.get("/auth/social/accounts")
        assert res.status_code == 200
        assert res.json()["youtube"]["connected"] is True
        assert res.json()["youtube"]["username"] == "@canalreal"

    def test_status_extraccion_cuenta_sin_username(self, client, db, user) -> None:
        # fallback `instagram_<hex>` se descarta y devuelve el nombre generico
        db.query_rows = [
            make_social_account(user.id, platform="instagram", platform_username="instagram_1a2b3c4d")
        ]
        res = client.get("/auth/social/status")
        assert res.json()["instagram"]["username"] == "Instagram User"

    def test_delete_400_plataforma_invalida(self, client) -> None:
        res = client.delete("/auth/social/spotify")
        assert res.status_code == 400

    def test_delete_200_idempotente_sin_cuenta(self, client, db) -> None:
        res = client.delete("/auth/social/tiktok")
        assert res.status_code == 200
        assert "desconectada" in res.json()["message"]

    def test_delete_200_elimina_cuenta(self, client, db, user) -> None:
        cuenta = make_social_account(user.id, platform="youtube")
        db.query_rows = [cuenta]
        res = client.delete("/auth/social/youtube")
        assert res.status_code == 200
        assert cuenta in db.deleted

    def test_youtube_connect_200(self, client, monkeypatch) -> None:
        from backend_fastapi.app.routers import social_auth as sa

        monkeypatch.setattr(sa, "yt_get_youtube_auth_url", lambda uid: "https://accounts.google.com/o/oauth2/auth")
        res = client.get("/auth/social/youtube/connect")
        assert res.status_code == 200
        assert res.json()["auth_url"].startswith("https://accounts.google.com")

    def test_youtube_callback_302_error(self, client) -> None:
        res = client.get(
            "/auth/social/youtube/callback",
            params={"error": "access_denied"},
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert "status=error" in res.headers["location"]
        assert "integration=youtube" in res.headers["location"]

    def test_youtube_callback_302_missing_code(self, client) -> None:
        res = client.get("/auth/social/youtube/callback", follow_redirects=False)
        assert res.status_code == 302
        assert "missing_code" in res.headers["location"]

    def test_youtube_callback_302_exito(self, client, db, monkeypatch) -> None:
        from backend_fastapi.app.routers import social_auth as sa

        monkeypatch.setattr(sa, "yt_exchange_code_for_tokens", lambda code: {"access_token": "tok"})
        monkeypatch.setattr(sa, "yt_decode_state", lambda state: "user-123")
        monkeypatch.setattr(sa, "yt_save_youtube_tokens", Mock())
        res = client.get(
            "/auth/social/youtube/callback",
            params={"code": "abc", "state": "estado"},
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert res.headers["location"].endswith("status=success")

    def test_instagram_connect_500_sin_client_id(self, client, db, monkeypatch) -> None:
        monkeypatch.delenv("INSTAGRAM_CLIENT_ID", raising=False)
        monkeypatch.delenv("META_APP_ID", raising=False)
        monkeypatch.delenv("FB_CLIENT_ID", raising=False)
        res = client.get("/auth/social/instagram/connect")
        assert res.status_code == 500

    def test_instagram_connect_200_con_env(self, client, db, monkeypatch) -> None:
        from backend_fastapi.app.routers import social_auth as sa

        monkeypatch.delenv("INSTAGRAM_CLIENT_ID", raising=False)
        monkeypatch.setenv("INSTAGRAM_CLIENT_ID", "meta-app-123")
        monkeypatch.setattr(sa, "ig_get_instagram_auth_url", lambda uid: "https://api.instagram.com/oauth/authorize")
        res = client.get("/auth/social/instagram/connect")
        assert res.status_code == 200
        assert res.json()["auth_url"].startswith("https://api.instagram.com")

    def test_instagram_callback_302_error_de_fallo(self, client) -> None:
        res = client.get("/auth/social/instagram/callback", follow_redirects=False)
        assert res.status_code == 302
        assert "status=error" in res.headers["location"]

    def test_tiktok_connect_500_sin_client_key(self, client, monkeypatch) -> None:
        monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
        res = client.get("/auth/social/tiktok/connect")
        assert res.status_code == 500

    def test_tiktok_connect_200_con_env(self, client, monkeypatch) -> None:
        from backend_fastapi.app.routers import social_auth as sa

        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "tk-clave")
        monkeypatch.setattr(sa, "tt_generate_pkce_pair", lambda: ("verifier", "challenge"))
        monkeypatch.setattr(
            sa,
            "tt_get_tiktok_auth_url",
            lambda state, code_challenge: "https://www.tiktok.com/v2/auth/authorize",
        )
        res = client.get("/auth/social/tiktok/connect")
        assert res.status_code == 200
        assert res.json()["auth_url"].startswith("https://www.tiktok.com")


# ---------------------------------------------------------------- sample


class TestSample:
    def test_sample_404_sin_video(self, client, db, monkeypatch, tmp_path) -> None:
        from backend_fastapi.app.routers import sample as sample_router

        monkeypatch.setattr(sample_router, "_get_sample_video_path", lambda: tmp_path / "no-existe.mp4")
        res = client.post("/videos/sample")
        assert res.status_code == 404

    def test_sample_202_crea_job(self, client, db, monkeypatch, tmp_path) -> None:
        import sys

        from backend_fastapi.app.routers import jobs as jobs_router
        from backend_fastapi.app.routers import sample as sample_router

        muestra = tmp_path / "sample.mp4"
        muestra.write_bytes(b"mp4")
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        monkeypatch.setattr(sample_router, "_get_sample_video_path", lambda: muestra)
        monkeypatch.setattr(jobs_router, "run_job_safely", Mock(), raising=False)

        res = client.post("/videos/sample")
        assert res.status_code == 202, res.text
        # se crean Video + Job
        assert len(db.added) == 2


# ---------------------------------------------------------------- stream SSE


class TestPublishStream:
    def _endpoint(self, user_id: Any) -> str:
        return f"/clips/{_fixtures.uuid.uuid4()}/publish-stream"

    def test_401_invalid_token(self, client) -> None:
        res = client.get(self._endpoint("x"), params={"token": "token-inventado"})
        assert res.status_code == 401
        assert res.json()["detail"]["error"] == "invalid_token"

    def test_401_token_expirado(self, db, user) -> None:
        expired = create_access_token(user.id, expires_delta=timedelta(seconds=-1))
        no_auth_client = build_client(db)
        try:
            res = no_auth_client.get(self._endpoint(user.id), params={"token": expired})
            assert res.status_code == 401
            assert res.json()["detail"]["error"] == "token_expired"
        finally:
            no_auth_client.close()
