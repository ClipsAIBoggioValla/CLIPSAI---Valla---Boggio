"""Cobertura unitaria del servicio de re-trim (Issue #121)."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from _fixtures import FakeSession, make_clip, make_job, make_video

from backend.core.schemas import RenderConfig
from backend_fastapi.app.routers import retrim as retrim_router
from backend_fastapi.app.services import retrim_service


def _plan(tmp_path: Path, hook=None, config=None) -> retrim_service.RetrimPlan:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"src")
    return retrim_service.RetrimPlan(
        source=source,
        start=10.0,
        end=20.0,
        cues=[{"start": 10.0, "end": 12.0, "text": "hola"}],
        hook=hook,
        config=config or RenderConfig(),
        title="Clip",
    )


def _seed(db, user, tmp_path: Path, **clip_overrides):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    clip_file = tmp_path / "clip.mp4"
    clip_file.write_bytes(b"old")
    video = make_video(user.id, filepath=str(source), file_path=str(source), transcript="hola transcript")
    job = make_job(video.id, result_metadata={"transcription_segments": [{"start": 10, "end": 20, "text": "hola"}]})
    clip = make_clip(job.id, video_id=video.id, storage_path=str(clip_file), start_time=10.0, end_time=45.0, **clip_overrides)
    db.seed(video, job, clip)
    return video, job, clip


def test_retrim_count_tolera_tags_invalidos() -> None:
    clip = make_clip(uuid.uuid4(), tags={"_retrim": {"count": "no-numero"}})
    assert retrim_service.retrim_count(clip) == 0


def test_owner_path_fallbacks() -> None:
    assert retrim_service._owner_path(None) is None
    assert retrim_service._owner_path(SimpleNamespace(file_path="x.mp4")) == Path("x.mp4")
    assert retrim_service._owner_path(SimpleNamespace(filepath=None, file_path=None)) is None


def test_select_source_sin_candidatos() -> None:
    clip = make_clip(uuid.uuid4(), storage_path="/no/existe.mp4")
    with pytest.raises(HTTPException) as exc:
        retrim_service.select_source(clip, None, None)
    assert exc.value.status_code == 404


def test_validate_window_excede_fuente() -> None:
    assert retrim_service._exceeds_source(10, None) is False
    with pytest.raises(HTTPException) as exc:
        retrim_service.validate_window(10, 30, 20)
    assert exc.value.status_code == 422


def test_cue_helpers_validan_errores() -> None:
    with pytest.raises(HTTPException):
        retrim_service._cue_times({"start": "x", "end": 1})
    assert retrim_service._cue_in_window(5, 6, (10, 15)) is False
    assert retrim_service._cue_text({"text": None}) == ""
    for cue in (
        {"start": 10, "end": 11, "text": ""},
        {"start": 11, "end": 10, "text": "x"},
        {"start": 5, "end": 11, "text": "x"},
    ):
        with pytest.raises(HTTPException):
            retrim_service._normalize_cue(cue, (10, 20))
    with pytest.raises(HTTPException):
        retrim_service._normalize_cues([{}] * 501, (10, 20))


def test_text_helpers_y_limites() -> None:
    assert retrim_service._split_sentences("uno\ndos") == ["uno", "dos"]
    assert retrim_service._split_sentences("") == []
    assert retrim_service._chunk_text("uno dos tres", max_chars=3) == ["uno", "dos", "tres"]
    assert len(retrim_service._limit_pieces(["a", "b", "c", "d"], 0.3)) <= 2
    with pytest.raises(HTTPException):
        retrim_service._cues_from_text("", (10, 20))


def test_segment_helpers() -> None:
    assert retrim_service._seg_times({"start": "x"}) is None
    assert retrim_service._seg_in_window({"start": 1, "end": 2, "text": ""}, (0, 10)) is None
    assert retrim_service._seg_in_window({"start": 1, "end": 2, "text": "x"}, (5, 10)) is None
    cues = retrim_service._cues_from_segments([{"start": 5, "end": 15, "text": "x"}], (10, 12))
    assert cues == [{"start": 10, "end": 12, "text": "x"}]


def test_original_segments_y_fallback() -> None:
    video = SimpleNamespace(transcript="00:00:00 - hola")
    assert retrim_service._original_segments(SimpleNamespace(result_metadata=[]), video)
    assert retrim_service._result_segments(SimpleNamespace(result_metadata=[])) == []
    clip = make_clip(uuid.uuid4(), title="Titulo", transcript=None)
    assert retrim_service._fallback_text(clip) == "Titulo"


def test_resolve_cues_prioriza_cues_y_shift() -> None:
    body = SimpleNamespace(
        start_time=10.0,
        end_time=20.0,
        subtitle_cues=[SimpleNamespace(start=11.0, end=12.0, text="nuevo")],
        subtitles_text="ignorado",
    )
    clip = make_clip(uuid.uuid4())
    cues = retrim_service.resolve_cues(body, clip, None, None)
    assert cues == [{"start": 11.0, "end": 12.0, "text": "nuevo"}]
    assert retrim_service._shift_cues(cues, 10.0)[0]["start"] == 1.0


def test_hook_helpers() -> None:
    assert retrim_service._hook_times({}) is None
    assert retrim_service._valid_hook(None) is None
    assert retrim_service._valid_hook((5, 4)) is None
    assert retrim_service.hook_window(make_clip(uuid.uuid4(), tags={"hook": {"applied": False}})) is None
    clip = make_clip(uuid.uuid4(), tags={"hook": {"applied": True, "mode": "in_clip", "start": 1, "end": 2}})
    assert retrim_service.hook_window(clip) is None


def test_watermark_path(tmp_path: Path) -> None:
    assert RenderConfig().watermark is False
    assert retrim_service._watermark_path(RenderConfig()) is None
    with pytest.raises(HTTPException):
        retrim_service._watermark_path(RenderConfig(watermark_path="/no/existe.png"))
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")
    assert retrim_service._watermark_path(RenderConfig(watermark_path=str(logo))) == logo
    assert retrim_service._watermark_path(RenderConfig(watermark=False, watermark_path=str(logo))) is None


def test_filtros_de_escala_y_overlay() -> None:
    assert "scale=1080:1920" in retrim_service._scale_filter(1080, 1920, 30)
    assert "[outv]" in retrim_service._overlay_filter(1080, 1920, 30)
    assert "colorchannelmixer=aa=0.6" in retrim_service._overlay_filter(1080, 1920, 30)


def test_run_finalize_ok_y_error(tmp_path: Path, monkeypatch) -> None:
    ok = SimpleNamespace(returncode=0, stderr=b"")
    run = Mock(return_value=ok)
    monkeypatch.setattr(retrim_service.subprocess, "run", run)
    retrim_service._run_finalize(tmp_path / "r.mp4", tmp_path / "f.mp4", (1080, 1920, 30), None)
    assert "-vf" in run.call_args.args[0]
    retrim_service._run_finalize(tmp_path / "r.mp4", tmp_path / "f.mp4", (1080, 1920, 30), tmp_path / "w.png")
    assert "-filter_complex" in run.call_args.args[0]

    monkeypatch.setattr(retrim_service.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=1, stderr=b"boom")))
    with pytest.raises(HTTPException) as exc:
        retrim_service._run_finalize(tmp_path / "r.mp4", tmp_path / "f.mp4", (1080, 1920, 30), None)
    assert exc.value.status_code == 500


def test_video_fps(monkeypatch) -> None:
    monkeypatch.setattr(retrim_service.subprocess, "run", Mock(return_value=SimpleNamespace(stdout="30/1")))
    assert retrim_service._video_fps(Path("x.mp4")) == 30.0
    monkeypatch.setattr(retrim_service.subprocess, "run", Mock(return_value=SimpleNamespace(stdout="invalido")))
    assert retrim_service._video_fps(Path("x.mp4")) is None


def test_finalize_default_y_custom(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(retrim_service, "_video_fps", lambda _path: 30.0)
    rendered = tmp_path / "rendered.mp4"
    rendered.write_bytes(b"v")
    final = tmp_path / "final.mp4"
    retrim_service._finalize(rendered, final, RenderConfig())
    assert final.read_bytes() == b"v"

    rendered2 = tmp_path / "rendered2.mp4"
    rendered2.write_bytes(b"v")
    run = Mock()
    monkeypatch.setattr(retrim_service, "_run_finalize", run)
    retrim_service._finalize(rendered2, tmp_path / "final2.mp4", RenderConfig(fps=25))
    run.assert_called_once()


def test_default_clips_dir_y_output_remoto(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_CLIPS_DIR", str(tmp_path))
    assert retrim_service._default_clips_dir() == tmp_path
    clip = make_clip(uuid.uuid4(), storage_path="https://cdn.example/clip.mp4")
    assert retrim_service._clip_output_path(clip).name == f"{clip.id}_retrim.mp4"


def test_require_output_y_cleanup(tmp_path: Path) -> None:
    with pytest.raises(HTTPException):
        retrim_service._require_output(tmp_path / "no.mp4")
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(HTTPException):
        retrim_service._require_output(empty)
    retrim_service._cleanup(tmp_path / "no.mp4")


def test_apply_result_hook_y_sin_hook(tmp_path: Path) -> None:
    db = FakeSession()
    clip = make_clip(uuid.uuid4(), tags={"hook": {"applied": True, "start": 1, "end": 2}})
    retrim_service._apply_result(db, clip, _plan(tmp_path), tmp_path / "out.mp4")
    assert clip.tags["hook"]["applied"] is False
    assert clip.tags["_render"] == "ass"

    clip2 = make_clip(uuid.uuid4(), tags={})
    retrim_service._apply_result(db, clip2, _plan(tmp_path, hook=(10.0, 15.0)), tmp_path / "out2.mp4")
    assert clip2.tags["hook"]["applied"] is True
    assert clip2.tags["_render"] == "hook+ass"


def test_clip_uuid_invalido() -> None:
    with pytest.raises(HTTPException) as exc:
        retrim_service.clip_uuid("no-es-uuid")
    assert exc.value.status_code == 422


def test_render_pipeline_llama_servicios(tmp_path: Path, monkeypatch) -> None:
    calls = {}
    for name in ("_render_trimmed", "_write_ass", "_finalize"):
        calls[name] = Mock()
        monkeypatch.setattr(retrim_service, name, calls[name])
    calls["reframe"] = Mock()
    calls["burn"] = Mock()
    monkeypatch.setattr(retrim_service.editor, "reframe_video", calls["reframe"])
    monkeypatch.setattr(retrim_service.ffmpeg_service, "burn_subtitles", calls["burn"])

    retrim_service._render_pipeline(_plan(tmp_path), tmp_path / "out.mp4")

    for name in ("_render_trimmed", "_write_ass", "_finalize", "reframe", "burn"):
        calls[name].assert_called_once()


def test_render_trimmed_hook_y_cut(tmp_path: Path, monkeypatch) -> None:
    hook_render = Mock()
    cut_render = Mock()
    monkeypatch.setattr(retrim_service.ffmpeg_service, "build_hook_clip", hook_render)
    monkeypatch.setattr(retrim_service.ffmpeg_service, "cut_segment", cut_render)
    retrim_service._render_trimmed(_plan(tmp_path, hook=(10.0, 15.0)), tmp_path / "a.mp4")
    retrim_service._render_trimmed(_plan(tmp_path), tmp_path / "b.mp4")
    hook_render.assert_called_once()
    cut_render.assert_called_once()


def test_write_ass_hook_y_sin_hook(tmp_path: Path, monkeypatch) -> None:
    hooked = Mock()
    simple = Mock()
    monkeypatch.setattr(retrim_service.ass_generator, "generate_hooked_ass", hooked)
    monkeypatch.setattr(retrim_service.ass_generator, "write_ass_file", simple)
    retrim_service._write_ass(_plan(tmp_path, hook=(10.0, 15.0)), tmp_path / "a.ass")
    retrim_service._write_ass(_plan(tmp_path), tmp_path / "b.ass")
    hooked.assert_called_once()
    simple.assert_called_once()


def test_execute_retrim_sin_salida(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(retrim_service, "_render_pipeline", Mock())
    clip = make_clip(uuid.uuid4(), storage_path=str(tmp_path / "clip.mp4"))
    with pytest.raises(HTTPException):
        retrim_service.execute_retrim(FakeSession(), clip, _plan(tmp_path))


def test_request_validate_range_y_cue_invalido() -> None:
    for end in (10.0, 14.0, 101.0):
        with pytest.raises(ValueError):
            retrim_router.RetrimRequest(start_time=10.0, end_time=end).validate_range()
    with pytest.raises(ValidationError):
        retrim_router.SubtitleCue(start=5, end=4, text="x")
    assert retrim_router._safe_style("inventado") == retrim_service.DEFAULT_CAPTION_STYLE


def test_load_owned_clip_404(client, db, user, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(retrim_router, "probe_duration", lambda _source: 120.0)
    response = client.post(f"/clips/{uuid.uuid4()}/retrim", json={"start_time": 10.0, "end_time": 30.0})
    assert response.status_code == 404

    video = make_video(uuid.uuid4(), filepath=str(tmp_path / "v.mp4"))
    job = make_job(video.id)
    clip = make_clip(job_id=None, video_id=video.id)
    db.seed(video, job, clip)
    response = client.post(f"/clips/{clip.id}/retrim", json={"start_time": 10.0, "end_time": 30.0})
    assert response.status_code == 404


def test_options_fallback_transcript(client, db, user, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(retrim_router, "probe_duration", lambda _source: 120.0)
    video = make_video(user.id, filepath=str(tmp_path / "v.mp4"), transcript="hola transcript")
    job = make_job(video.id, result_metadata={})
    clip = make_clip(
        job.id,
        video_id=video.id,
        transcript="hola transcript",
        tags={"_retrim": {"caption_style": "inventado"}},
    )
    (tmp_path / "v.mp4").write_bytes(b"v")
    db.seed(video, job, clip)

    response = client.get(f"/clips/{clip.id}/retrim/options")

    assert response.status_code == 200
    body = response.json()
    assert body["subtitles_text"] == "hola transcript"
    assert body["default_caption_style"] == retrim_service.DEFAULT_CAPTION_STYLE


def test_retrim_con_cues_y_hook_aplicado(client, db, user, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(retrim_router, "probe_duration", lambda _source: 120.0)
    captured = {}

    def _fake_render(plan, output: Path) -> None:
        captured["plan"] = plan
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"new")

    monkeypatch.setattr(retrim_service, "_render_pipeline", _fake_render)
    _video, _job, clip = _seed(db, user, tmp_path, tags={"hook": {"applied": True, "mode": "teaser", "start": 10, "end": 15}})

    response = client.post(
        f"/clips/{clip.id}/retrim",
        json={"start_time": 10.0, "end_time": 40.0, "subtitle_cues": [{"start": 11.0, "end": 12.0, "text": "nuevo"}]},
    )

    assert response.status_code == 200, response.text
    assert captured["plan"].hook == (10.0, 15.0)
    assert captured["plan"].cues[0]["text"] == "nuevo"


def test_retrim_sin_hook_por_config(client, db, user, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(retrim_router, "probe_duration", lambda _source: 120.0)
    captured = {}

    def _fake_render(plan, output: Path) -> None:
        captured["plan"] = plan
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"new")

    monkeypatch.setattr(retrim_service, "_render_pipeline", _fake_render)
    _video, _job, clip = _seed(db, user, tmp_path, tags={"hook": {"applied": True, "mode": "teaser", "start": 10, "end": 15}})

    response = client.post(
        f"/clips/{clip.id}/retrim",
        json={"start_time": 10.0, "end_time": 40.0, "render_config": {"enable_hook_teaser": False}},
    )

    assert response.status_code == 200, response.text
    assert captured["plan"].hook is None
