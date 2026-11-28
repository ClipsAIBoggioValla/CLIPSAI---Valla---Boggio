"""Tests de hardening HTTP y redacción de logs (compuerta ASH)."""

from __future__ import annotations

import logging
import uuid
from unittest.mock import Mock

from _fixtures import build_client, make_clip, make_job

from backend_fastapi.app.core import security_middleware as sm
from backend_fastapi.app.core.logging_security import RedactionFilter, redact
from backend_fastapi.app.routers.clips import _public_download_allowed
from backend_fastapi.app.services.media_signing import signed_query, verify_signed_query


def test_security_headers_presentes(client) -> None:
    res = client.get("/health")

    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["x-request-id"]


def test_csp_request_id_y_permissions_policy(client) -> None:
    res = client.get("/health")

    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in res.headers
    assert "content-security-policy" in res.headers


def test_request_id_se_respeta_si_es_seguro(client) -> None:
    res = client.get("/health", headers={"X-Request-ID": "review-123"})

    assert res.headers["x-request-id"] == "review-123"


def test_cors_rechaza_origen_no_permitido(client) -> None:
    res = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in res.headers
    assert res.headers.get("access-control-allow-credentials") != "true"


def test_cors_acepta_origen_local_permitido(client) -> None:
    res = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )

    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert res.headers.get("access-control-allow-credentials") != "true"


def test_rate_limit_global_devuelve_429(client) -> None:
    original = sm.security_limiter.max_requests
    sm.security_limiter.max_requests = 1
    sm.reset_security_limiter()
    try:
        assert client.get("/clips").status_code == 200
        limited = client.get("/clips")
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "60"
    finally:
        sm.security_limiter.max_requests = original
        sm.reset_security_limiter()


def test_descarga_publica_solo_para_publicados() -> None:
    assert not _public_download_allowed(make_clip(uuid.uuid4(), publication_status="draft"))
    assert _public_download_allowed(make_clip(uuid.uuid4(), publication_status="published"))
    assert _public_download_allowed(make_clip(uuid.uuid4(), publication_status=None, status="PUBLISHING"))


def test_descarga_sin_auth_rechaza_clip_no_publicado(db) -> None:
    clip = make_clip(uuid.uuid4(), publication_status="draft", storage_path="/tmp/no-existe.mp4")
    db.seed(clip)
    anon = build_client(db, use_real_auth=True)
    res = anon.get(f"/clips/{clip.id}/descarga")

    assert res.status_code == 401


def test_webhook_duplicado_es_idempotente(db, monkeypatch) -> None:
    from backend_fastapi.app.routers import jobs as jobs_router
    from backend_fastapi.app.routers import webhooks

    job = make_job(uuid.uuid4(), status="completed")
    db.seed(job)
    persist = Mock()
    monkeypatch.setattr(jobs_router, "_persistir_clips_r2", persist)

    result = webhooks._aplicar_callback(db, {"job_id": str(job.id), "status": "COMPLETED", "output": {}})

    assert result == {"received": True}
    persist.assert_not_called()


def test_firma_de_clip_valida_y_rechaza_otro_id() -> None:
    from urllib.parse import parse_qs

    params = parse_qs(signed_query("clip-123"))
    exp, sig = params["exp"][0], params["sig"][0]

    assert verify_signed_query("clip-123", exp, sig)
    assert not verify_signed_query("clip-otro", exp, sig)
    assert not verify_signed_query("clip-123", "0", sig)


def test_descarga_con_firma_permite_clip_no_publicado(db, tmp_path) -> None:
    from urllib.parse import parse_qs

    archivo = tmp_path / "clip.mp4"
    archivo.write_bytes(b"video")
    clip = make_clip(uuid.uuid4(), publication_status="draft", storage_path=str(archivo))
    db.seed(clip)
    anon = build_client(db, use_real_auth=True)
    params = parse_qs(signed_query(str(clip.id)))
    res = anon.get(f"/clips/{clip.id}/descarga?exp={params['exp'][0]}&sig={params['sig'][0]}")

    assert res.status_code == 200


def _json_con_tokens() -> str:
    clave = "access_token"
    refresh = "refresh_token"
    valor = "token-secreto"
    return "{" + f'"{clave}":"{valor}","{refresh}":"{valor}"' + "}"


def test_redacta_tokens_en_json() -> None:
    salida = redact(_json_con_tokens())

    assert "token-secreto" not in salida
    assert "access_token" in salida


def test_redacta_tokens_en_urls_y_bearer() -> None:
    assert "token-secreto" not in redact("https://api.test/cb?access_token=token-secreto&x=1")
    assert "Bearer abc.def" not in redact("Authorization: Bearer abc.def")


def test_filtro_redacta_args_del_log() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="respuesta=%s",
        args=(_json_con_tokens(),),
        exc_info=None,
    )
    RedactionFilter().filter(record)

    assert "token-secreto" not in record.getMessage()
