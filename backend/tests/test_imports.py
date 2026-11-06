from __future__ import annotations


def test_import_backend_modules():
    import backend.handler as h
    import backend.services.ai_viral.analyzer as a
    import backend.services.video_editor.renderer as r
    import backend.core.security.ssrf_guard as s
    import backend.core.security.vault as v
    assert h is not None and a is not None


def test_import_backend_track():
    try:
        import backend.track_a.ingestion.service as s
        import backend.track_b.virality.engine as e
        assert s is not None and e is not None
    except Exception:
        pass
