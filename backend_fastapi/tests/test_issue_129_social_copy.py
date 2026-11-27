from __future__ import annotations

import uuid
from types import SimpleNamespace

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.services import claude_service


def test_social_copy_schema_adds_platform_fields_without_requiring_them() -> None:
    item = claude_service._build_output_schema(["S_1"])["properties"]["clips"]["items"]
    properties = item["properties"]

    assert properties["tiktok_caption"]["maxLength"] == 500
    assert properties["reels_caption"]["maxLength"] == 500
    assert properties["shorts_title"]["maxLength"] == 100
    assert properties["hashtags"]["properties"]["shorts"]["maxItems"] == 5
    assert "tiktok_caption" not in item["required"]


def test_social_copy_fallback_is_deterministic_without_llm() -> None:
    fallback = claude_service.fallback_social_copy("Una historia inesperada")

    assert fallback["tiktok_caption"] == "Una historia inesperada"
    assert fallback["reels_caption"] == "Una historia inesperada"
    assert fallback["shorts_title"] == "Una historia inesperada"
    assert fallback["hashtags"] == {
        "tiktok": ["#parati", "#viral", "#clipsai"],
        "reels": ["#reels", "#viral", "#clipsai"],
        "shorts": ["#shorts", "#viral", "#clipsai"],
    }


def test_normalize_social_copy_caps_lengths_and_cleans_hashtags() -> None:
    normalized = claude_service.normalize_social_copy(
        "Título",
        {"shorts_title": "S" * 150, "hashtags": {"tiktok": ["#tema!?", "sin_espacios"]}},
    )

    assert len(normalized["shorts_title"]) == 100
    assert normalized["hashtags"]["tiktok"] == ["#tema", "#sin_espacios"]
    assert normalized["hashtags"]["reels"] == ["#reels", "#viral", "#clipsai"]


def test_social_copy_is_saved_under_clip_tags_and_handles_legacy_items() -> None:
    datos = jobs_router._parsear_clip_item(
        {
            "title": "Momento viral",
            "start": 0,
            "end": 30,
            "score": 8,
            "tags": {
                "legacy_meta": "preservada",
                "social_copy": {
                    "tiktok_caption": "Copy TikTok",
                    "reels_caption": "Copy Reels",
                    "shorts_title": "Título Shorts",
                    "hashtags": {"tiktok": ["#tema"]},
                },
            },
        },
        0,
    )
    tags = jobs_router._base_tags_de(datos["tags"], datos["social_copy"])
    clip = jobs_router._crear_clip_persistible(
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
        datos,
        tags,
        None,
        "clip.mp4",
    )

    assert clip.tags["legacy_meta"] == "preservada"
    assert clip.tags["social_copy"] == {
        "tiktok_caption": "Copy TikTok",
        "reels_caption": "Copy Reels",
        "shorts_title": "Título Shorts",
        "hashtags": {
            "tiktok": ["#tema"],
            "reels": ["#reels", "#viral", "#clipsai"],
            "shorts": ["#shorts", "#viral", "#clipsai"],
        },
    }


def test_claude_clip_validation_normalizes_legacy_result() -> None:
    valid = claude_service._validar_clip_candidato(
        {
            "start_sentence_id": "S_1",
            "end_sentence_id": "S_1",
            "score": 8,
            "title": "Clip",
            "hook_candidates": [],
            "has_hook": False,
        }
    )

    assert valid is not None
    assert valid["social_copy"] == claude_service.fallback_social_copy("Clip")
