"""Pruebas de autenticación HMAC para callbacks de RunPod (Issue #113)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from _fixtures import make_job, make_video
from backend_fastapi.app.config import get_settings


SECRET = "runpod-webhook-secret-test"


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _cuerpo_callback(job_id, state="COMPLETED") -> bytes:
    return json.dumps(
        {
            "job_id": str(job_id),
            "status": state,
            "output": {
                "clips": [
                    {
                        "url_r2": "https://storage.test/clip.mp4",
                        "start_time": 3,
                        "end_time": 18,
                    }
                ]
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _firma(raw: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def _set_secret(monkeypatch, secret: str = SECRET) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RUNPOD_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()


def _seed_job(db, user):
    video = make_video(user.id)
    job = make_job(video.id, status="processing", progress=35)
    db.seed(video, job)
    return job


@pytest.mark.parametrize(
    ("header", "prefix"),
    [
        ("X-Runpod-Signature", ""),
        ("X-Runpod-Signature", "sha256="),
        ("X-Webhook-Signature", ""),
        ("X-Webhook-Signature", "sha256="),
    ],
)
def test_firma_valida_persiste_clips_r2(client, db, user, monkeypatch, header, prefix) -> None:
    _set_secret(monkeypatch)
    job = _seed_job(db, user)
    raw = _cuerpo_callback(job.id)

    response = client.post(
        "/webhooks/runpod",
        content=raw,
        headers={header: f"{prefix}{_firma(raw)}"},
    )

    assert response.status_code == 202, response.text
    assert job.status == "completed"
    assert job.progress == 100
    assert len(db.added) == 1
    assert db.commits == 1


@pytest.mark.parametrize("signature", [None, "0" * 64, "sha256=not-a-digest"])
def test_firma_ausente_invalida_o_malformada_no_muta_db(client, db, monkeypatch, signature) -> None:
    _set_secret(monkeypatch)
    raw = _cuerpo_callback("d61d1bd6-32b8-4a8a-9a03-a9722aa8f784")
    headers = {"X-Runpod-Signature": signature} if signature is not None else {}

    response = client.post("/webhooks/runpod", content=raw, headers=headers)

    assert response.status_code == 401
    assert db.commits == 0
    assert db.added == []


def test_secret_vacio_en_development_acepta_sin_firma(client, db, user, monkeypatch) -> None:
    _set_secret(monkeypatch, "")
    job = _seed_job(db, user)

    response = client.post("/webhooks/runpod", content=_cuerpo_callback(job.id))

    assert response.status_code == 202
    assert job.status == "completed"
    assert len(db.added) == 1


def test_json_invalido_firmado_no_muta_db(client, db, monkeypatch) -> None:
    _set_secret(monkeypatch)
    raw = b"not-json"

    response = client.post(
        "/webhooks/runpod",
        content=raw,
        headers={"X-Runpod-Signature": _firma(raw)},
    )

    assert response.status_code == 400
    assert db.commits == 0
    assert db.added == []


def test_estado_fallido_actualiza_job(client, db, user, monkeypatch) -> None:
    _set_secret(monkeypatch)
    job = _seed_job(db, user)
    raw = _cuerpo_callback(job.id, state="TIMED_OUT")

    response = client.post(
        "/webhooks/runpod",
        content=raw,
        headers={"X-Runpod-Signature": _firma(raw)},
    )

    assert response.status_code == 202
    assert job.status == "failed"
    assert "TIMED_OUT" in job.error_message
    assert db.commits == 1
    assert db.added == []


def test_job_inexistente_devuelve_404_sin_mutacion(client, db, monkeypatch) -> None:
    _set_secret(monkeypatch)
    raw = _cuerpo_callback("d61d1bd6-32b8-4a8a-9a03-a9722aa8f784")

    response = client.post(
        "/webhooks/runpod",
        content=raw,
        headers={"X-Runpod-Signature": _firma(raw)},
    )

    assert response.status_code == 404
    assert db.commits == 0
    assert db.added == []
