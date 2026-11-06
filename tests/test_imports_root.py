from __future__ import annotations


def test_import_root_modules():
    import main as m
    import engine as e
    import engine_subprocess as es
    import editor_viral as ev
    import whisper_transcriber as wt
    import limpiar as l
    assert m is not None and e is not None


def test_import_app_services():
    import app.services.hook_service as h
    import app.services  # noqa
    assert h is not None


def test_import_backend_modules():
    import backend.handler as h
    import backend.services.ai_viral.analyzer as a
    assert h is not None and a is not None
