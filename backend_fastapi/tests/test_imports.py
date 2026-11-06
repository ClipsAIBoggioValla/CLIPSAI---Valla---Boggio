from __future__ import annotations


def test_import_core_modules():
    import backend_fastapi.app.main as m
    import backend_fastapi.app.config as c
    import backend_fastapi.app.database as d
    import backend_fastapi.app.deps as dep
    import backend_fastapi.app.cli as cli
    import backend_fastapi.app.security.hashing as h
    import backend_fastapi.app.security.jwt as j
    assert m is not None and c is not None


def test_import_services():
    import backend_fastapi.app.services.engine as e
    import backend_fastapi.app.services.ffmpeg_service as f
    import backend_fastapi.app.services.hook_service as h
    import backend_fastapi.app.services.whisper_service as w
    import backend_fastapi.app.services.claude_service as c
    import backend_fastapi.app.services.ass_generator as a
    import backend_fastapi.app.services.transcript_utils as t
    import backend_fastapi.app.services.social_common as sc
    import backend_fastapi.app.services.publish_service as p
    import backend_fastapi.app.services.tiktok_service as tk
    import backend_fastapi.app.services.instagram_service as ig
    import backend_fastapi.app.services.youtube_service as yt
    import backend_fastapi.app.services.runpod_service as rp
    import backend_fastapi.app.services.editor as ed
    import backend_fastapi.app.services.social_common as sc2
    assert e is not None


def test_import_routers():
    import backend_fastapi.app.routers.auth as a
    import backend_fastapi.app.routers.videos as v
    import backend_fastapi.app.routers.jobs as j
    import backend_fastapi.app.routers.clips as c
    import backend_fastapi.app.routers.publish as p
    import backend_fastapi.app.routers.metrics as m
    import backend_fastapi.app.routers.stats as s
    import backend_fastapi.app.routers.users as u
    import backend_fastapi.app.routers.sample as sa
    import backend_fastapi.app.routers.stream as st
    import backend_fastapi.app.routers.subtitles as sub
    import backend_fastapi.app.routers.social_auth as sa2
    import backend_fastapi.app.routers.export as ex
    assert a is not None


def test_import_models():
    import backend_fastapi.app.models as m
    import backend_fastapi.app.models.clip as c
    import backend_fastapi.app.models.job as j
    import backend_fastapi.app.models.usuario as u
    import backend_fastapi.app.models.video as v
    import backend_fastapi.app.models.social_account as sa
    import backend_fastapi.app.models.mixins as mx
    assert m is not None


def test_import_tasks():
    import backend_fastapi.app.tasks.subtitle_pipeline as sp
    assert sp is not None
