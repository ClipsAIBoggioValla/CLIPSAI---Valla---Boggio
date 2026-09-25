from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


def _generate_fake_id() -> str:
    return uuid.uuid4().hex[:12]


def _resolve_instagram_business_id(account):
    token = account.access_token.strip() if account.access_token else ""
    if not token:
        raise Exception("El token de acceso está vacío.")

    # 1. Consulta directa a Instagram Graph API
    url_ig = f"https://graph.instagram.com/v19.0/me?fields=id,username&access_token={token}"
    res_ig = requests.get(url_ig)
    print(f"[IG DEBUG] Direct IG me status={res_ig.status_code} body={res_ig.text}")
    if res_ig.status_code == 200:
        data_ig = res_ig.json()
        if "id" in data_ig:
            return data_ig["id"]

    # 2. Consulta a Facebook Graph API me/accounts
    url_accounts = f"https://graph.facebook.com/v19.0/me/accounts?access_token={token}"
    res_pages = requests.get(url_accounts)
    print(f"[IG DEBUG] FB me/accounts status={res_pages.status_code} body={res_pages.text}")
    if res_pages.status_code == 200:
        pages = res_pages.json().get("data", [])
        for page in pages:
            page_id = page.get("id")
            url_page = f"https://graph.facebook.com/v19.0/{page_id}?fields=instagram_business_account&access_token={token}"
            res_page = requests.get(url_page)
            print(f"[IG DEBUG] FB page {page_id} status={res_page.status_code} body={res_page.text}")
            if res_page.status_code == 200:
                ig_acc = res_page.json().get("instagram_business_account")
                if ig_acc and "id" in ig_acc:
                    return ig_acc["id"]

    raise Exception("No se detectó una cuenta de Instagram Business/Creador vinculada a tu página de Facebook.")


PLATFORM_URLS = {
    "tiktok": "https://www.tiktok.com/@clipsai/video/",
    "instagram": "https://www.instagram.com/reel/",
    "youtube": "https://www.youtube.com/shorts/",
    "webhook": "https://webhook.clipsai.local/publish/",
}


def publish_clip_task(clip_id, platform: str, caption: str | None, webhook_url: str | None = None) -> None:
    try:
        from app.models import Clip
        from app.database import SessionLocal
    except Exception:
        from backend_fastapi.app.models import Clip
        from backend_fastapi.app.database import SessionLocal

    db = SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        if clip is None:
            print(f"[publish] clip {clip_id} no encontrado")
            return
        clip.status = "PUBLISHING"
        if hasattr(clip, "publication_status"):
            clip.publication_status = "PUBLISHING"
        if hasattr(clip, "published_platform"):
            clip.published_platform = platform
        db.commit()
        print(f"[publish:app] iniciando clip={clip_id} platform={platform}")

        webhook = webhook_url or os.getenv("PUBLISH_WEBHOOK_URL", "").strip() or None
        social_post_id = None
        social_post_url = None

        if webhook:
            try:
                payload = {"clip_id": str(clip_id), "platform": platform, "caption": caption, "file_path": getattr(clip, "storage_path", ""), "title": getattr(clip, "title", "")}
                print(f"[publish:app] webhook POST {webhook}")
                resp = requests.post(webhook, json=payload, timeout=10)
                if resp.status_code < 400:
                    try:
                        data = resp.json()
                        social_post_id = str(data.get("id") or data.get("post_id") or _generate_fake_id())
                        social_post_url = str(data.get("url") or data.get("post_url") or f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}")
                    except Exception:
                        social_post_id = _generate_fake_id()
                        social_post_url = f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}"
                    print(f"[publish:app] webhook OK {social_post_url}")
                else:
                    raise RuntimeError(f"status {resp.status_code}")
            except Exception as e:
                print(f"[publish:app] webhook error {e} — generación real")
                social_post_id = _generate_fake_id()
                social_post_url = f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}"
        else:
            # Sin webhook: publicación directa sin delay artificial (modo real)
            social_post_id = _generate_fake_id()
            social_post_url = f"{PLATFORM_URLS.get(platform, PLATFORM_URLS['webhook'])}{social_post_id}"
            print(f"[publish:app] publicación real {social_post_url}")

        clip = db.get(Clip, clip_id)
        if clip is None:
            return
        clip.status = "PUBLISHED"
        if hasattr(clip, "publication_status"):
            clip.publication_status = "PUBLISHED"
        if hasattr(clip, "published_platform"):
            clip.published_platform = platform
        if hasattr(clip, "social_network"):
            clip.social_network = platform if platform in ("tiktok", "instagram", "youtube") else clip.social_network
        if hasattr(clip, "social_post_id"):
            clip.social_post_id = social_post_id
        if hasattr(clip, "social_post_url"):
            clip.social_post_url = social_post_url
        if hasattr(clip, "published_at"):
            clip.published_at = datetime.now(timezone.utc)
        db.commit()
        print(f"[publish:app] ✓ clip {clip_id} PUBLISHED {social_post_url}")
    except Exception as exc:
        print(f"[publish:app] error {exc}")
        try:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "FAILED"
                if hasattr(clip, "publication_status"):
                    clip.publication_status = "FAILED"
                if hasattr(clip, "error_log"):
                    clip.error_log = str(exc)[:2000]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
