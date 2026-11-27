"""Tests del editor ligero de re-trim (Issue #121).

Sin FFmpeg, Whisper ni PostgreSQL reales: se mockea el pipeline de render y
se usan los fakes compartidos de `_fixtures.py`.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from _fixtures import make_clip, make_job, make_video

from backend_fastapi.app.routers import retrim as retrim_router
from backend_fastapi.app.services import retrim_service


def _seed(db, user, tmp_path: Path, **clip_overrides):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source-video")
    clip_file = tmp_path / "clip.mp4"
    clip_file.write_bytes(b"old-clip")
    video = make_video(user.id, filepath=str(source), file_path=str(source))
    job = make_job(
        video.id,
        result_metadata={"transcription_segments": [{"start": 10, "end": 20, "text": "hola mundo"}]},
    )
    clip = make_clip(
        job.id,
        video_id=video.id,
        storage_path=str(clip_file),
        start_time=10.0,
        end_time=45.0,
        **clip_overrides,
    )
    db.seed(video, job, clip)
    return source, clip_file, video, job, clip


def _fake_render(plan, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"new-clip")


def _patch_probe(monkeypatch, duration: float = 120.0) -> None:
    monkeypatch.setattr(retrim_router, "probe_duration", lambda _source: duration)


def test_retrim_actualiza_clip_y_preserva_publicacion(client, db, user, tmp_path, monkeypatch) -> None:
    _patch_probe(monkeypatch)
    monkeypatch.setattr(retrim_service, "_render_pipeline", _fake_render)
    _source, clip_file, _video, _job, clip = _seed(
        db,
        user,
        tmp_path,
        publication_status="published",
        social_post_url="https://tiktok.example/post/1",
        published_platform="tiktok",
    )

    response = client.post(
        f"/clips/{clip.id}/retrim",
        json={
            "start_time": 12.0,
            "end_time": 40.0,
            "subtitles_text": "Hola mundo. Esto es una prueba.",
            "render_config": {"caption_style": "neon_green"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["start_time"] == 12.0
    assert body["end_time"] == 40.0
    assert body["caption_style"] == "neon_green"
    assert body["retrim_count"] == 1
    assert clip_file.read_bytes() == b"new-clip"
    assert clip.publication_status == "published"
    assert clip.social_post_url == "https://tiktok.example/post/1"
    assert clip.published_platform == "tiktok"
    assert clip.tags["_retrim"]["count"] == 1
    assert clip.tags["ass"]["style"] == "neon_green"


def test_retrim_limite_de_ediciones(client, db, user, tmp_path, monkeypatch) -> None:
    _patch_probe(monkeypatch)
    _source, _clip_file, _video, _job, clip = _seed(
        db,
        user,
        tmp_path,
        tags={"has_ass": True, "_retrim": {"count": 3, "limit": 3}},
    )

    response = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 10.0, "end_time": 30.0})

    assert response.status_code == 429
    assert "límite" in response.json()["detail"].lower()


def test_retrim_libera_reserva_si_el_render_falla(client, db, user, tmp_path, monkeypatch) -> None:
    _patch_probe(monkeypatch)
    _source, _clip_file, _video, _job, clip = _seed(db, user, tmp_path)

    def _boom(_plan, _output: Path) -> None:
        raise RuntimeError("ffmpeg roto")

    monkeypatch.setattr(retrim_service, "_render_pipeline", _boom)

    with pytest.raises(RuntimeError):
        client.post(f"/clips/{clip.id}/retrim", json={"start_time": 10.0, "end_time": 30.0})

    assert retrim_service.retrim_count(clip) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"start_time": 10.0, "end_time": 14.0},
        {"start_time": 10.0, "end_time": 101.0},
        {"start_time": 10.0, "end_time": 30.0, "render_config": {"caption_style": "inventado"}},
    ],
)
def test_retrim_valida_rango_y_estilo(client, db, user, tmp_path, monkeypatch, payload) -> None:
    _patch_probe(monkeypatch)
    _source, _clip_file, _video, _job, clip = _seed(db, user, tmp_path)

    response = client.post(f"/clips/{clip.id}/retrim", json=payload)

    assert response.status_code == 422


def test_retrim_options_precarga_editor(client, db, user, tmp_path, monkeypatch) -> None:
    _patch_probe(monkeypatch)
    _source, _clip_file, _video, _job, clip = _seed(db, user, tmp_path)

    response = client.get(f"/clips/{clip.id}/retrim/options")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_duration"] == 120.0
    assert body["duration"] == 35.0
    assert body["subtitles_text"] == "hola mundo"
    assert body["retrim_limit"] == 3
    assert "karaoke_yellow" in body["caption_styles"]


def test_cues_desde_texto_respeta_ventana() -> None:
    cues = retrim_service._cues_from_text("Uno. Dos. Tres.", (10.0, 25.0))

    assert cues[0]["start"] == 10.0
    assert cues[-1]["end"] == 25.0
    assert all(cue["end"] > cue["start"] for cue in cues)


def test_hook_window_solo_teaser_aplicado() -> None:
    clip = make_clip(uuid.uuid4(), tags={"hook": {"applied": True, "mode": "teaser", "start": 12, "end": 17}})
    assert retrim_service.hook_window(clip) == (12.0, 17.0)

    clip.tags = {"hook": {"applied": True, "mode": "in_clip", "start": 12, "end": 17}}
    assert retrim_service.hook_window(clip) is None


def test_select_source_prefiere_video_original(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    clip_file = tmp_path / "clip.mp4"
    clip_file.write_bytes(b"clip")
    video = make_video(uuid.uuid4(), filepath=str(source))
    clip = make_clip(uuid.uuid4(), storage_path=str(clip_file))

    assert retrim_service.select_source(clip, None, video) == source


def test_max_retrims_configurable(monkeypatch) -> None:
    monkeypatch.setenv("RETRIM_MAX_PER_CLIP", "5")
    assert retrim_service.max_retrims() == 5
    monkeypatch.setenv("RETRIM_MAX_PER_CLIP", "invalido")
    assert retrim_service.max_retrims() == retrim_service.DEFAULT_MAX_RETRIMS
