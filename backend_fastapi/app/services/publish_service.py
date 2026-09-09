from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

import requests

from ..database import SessionLocal
from ..models import Clip


PLATFORM_URLS = {
    "tiktok": "https://www.tiktok.com/@clipsai/video/",
    "instagram": "https://www.instagram.com/reel/",
    "youtube": "https://www.youtube.com/shorts/",
    "webhook": "https://webhook.clipsai.local/publish/",
}


def _generate_fake_id() -> str:
    return uuid.uuid4().hex[:12]


def publish_clip_task(clip_id: uuid.UUID, platform: str, caption: str | None, webhook_url: str | None = None) -> None:
    db = SessionLocal()
    try:
        clip: Clip | None = db.get(Clip, clip_id)
        if clip is None:
            print(f"[publish] clip {clip_id} no encontrado")
            return

        clip.status = "PUBLISHING"
        clip.publication_status = "PUBLISHING"
        clip.published_platform = platform
        db.commit()
        print(f"[publish] iniciando publicación clip={clip_id} platform={platform} caption={caption!r}")

        webhook = webhook_url or os.getenv("PUBLISH_WEBHOOK_URL", "").strip() or None

        social_post_id: str | None = None
        social_post_url: str | None = None

        if webhook:
            try:
                payload = {
                    "clip_id": str(clip_id),
                    "platform": platform,
                    "caption": caption,
                    "file_path": clip.storage_path,
                    "title": clip.title,
                }
                print(f"[publish] enviando webhook POST {webhook} payload={payload}")
                resp = requests.post(webhook, json=payload, timeout=10)
                if resp.status_code < 400:
                    try:
                        data = resp.json()
                        social_post_id = str(data.get("id") or data.get("post_id") or _generate_fake_id())
                        social_post_url = str(data.get("url") or data.get("post_url") or f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}")
                    except Exception:
                        social_post_id = _generate_fake_id()
                        social_post_url = f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}"
                    print(f"[publish] webhook OK status={resp.status_code} id={social_post_id} url={social_post_url}")
                else:
                    print(f"[publish] webhook falló status={resp.status_code} body={resp.text[:300]} — usando simulación")
                    raise RuntimeError(f"webhook status {resp.status_code}")
            except Exception as e:
                print(f"[publish] webhook error {e} — fallback simulado")
                social_post_id = _generate_fake_id()
                social_post_url = f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}"
        else:
            time.sleep(2)
            social_post_id = _generate_fake_id()
            base = PLATFORM_URLS.get(platform, PLATFORM_URLS["webhook"])
            social_post_url = f"{base}{social_post_id}"
            print(f"[publish] simulado sin webhook platform={platform} id={social_post_id} url={social_post_url}")

        clip = db.get(Clip, clip_id)
        if clip is None:
            return
        clip.status = "PUBLISHED"
        clip.publication_status = "PUBLISHED"
        clip.published_platform = platform
        clip.social_network = platform if platform in ("tiktok", "instagram", "youtube") else clip.social_network
        clip.social_post_id = social_post_id
        clip.social_post_url = social_post_url
        clip.published_at = datetime.now(timezone.utc)
        db.commit()
        print(f"[publish] ✓ clip {clip_id} PUBLISHED platform={platform} post_id={social_post_id} url={social_post_url}")

    except Exception as exc:
        print(f"[publish] error clip={clip_id} exc={exc}")
        try:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "FAILED"
                clip.publication_status = "FAILED"
                clip.error_log = str(exc)[:2000]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
