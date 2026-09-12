from __future__ import annotations

import base64
import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import logging

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import SocialAccount

logger = logging.getLogger(__name__)

INSTAGRAM_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
]

META_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
META_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
META_LONG_LIVED_URL = "https://graph.facebook.com/oauth/access_token"

DEFAULT_REDIRECT_URI = "https://decorator-excretory-satin.ngrok-free.dev/auth/social/instagram/callback"


def _get_instagram_config() -> tuple[str, str, str]:
    client_id = os.getenv("INSTAGRAM_CLIENT_ID") or os.getenv("META_APP_ID") or os.getenv("FB_CLIENT_ID") or ""
    client_id = client_id.strip()
    client_secret = os.getenv("INSTAGRAM_CLIENT_SECRET") or os.getenv("META_APP_SECRET") or os.getenv("FB_CLIENT_SECRET") or ""
    client_secret = client_secret.strip()
    redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI
    return client_id, client_secret, redirect_uri


def _encode_state(user_id: str) -> str:
    payload = json.dumps({"user_id": str(user_id)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_state(state: str) -> str | None:
    if not state:
        return None
    padded = state + "=" * (-len(state) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            decoded = decoder(padded.encode()).decode()
            try:
                data = json.loads(decoded)
                if isinstance(data, dict) and "user_id" in data:
                    return str(data["user_id"])
            except Exception:
                pass
            return decoded
        except Exception:
            continue
    return state


def get_instagram_auth_url(user_id: str) -> str:
    client_id, _, redirect_uri = _get_instagram_config()
    if not client_id:
        raise ValueError("INSTAGRAM_CLIENT_ID / META_APP_ID no está configurado en el archivo .env del backend")
    state = _encode_state(str(user_id))
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
        "response_type": "code",
        "state": state or "",
    }
    return f"https://www.facebook.com/v18.0/dialog/oauth?{urllib.parse.urlencode(params)}"


def exchange_code_for_short_lived_token(code: str) -> dict[str, Any]:
    client_id, client_secret, redirect_uri = _get_instagram_config()
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    resp = requests.get(META_TOKEN_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def exchange_short_for_long_lived_token(short_token: str) -> dict[str, Any]:
    client_id, client_secret, _ = _get_instagram_config()
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "fb_exchange_token": short_token,
    }
    resp = requests.get(META_LONG_LIVED_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _fetch_instagram_username(access_token: str) -> str | None:
    display_name: str | None = None
    try:
        url = f"https://graph.facebook.com/v18.0/me?fields=id,name&access_token={access_token}"
        logger.info("[META API CALL] Requesting %s", url.replace(access_token, "HIDDEN_TOKEN"))
        res = requests.get(url, timeout=10)
        logger.info("[META /me STATUS]: %s | [BODY]: %s", res.status_code, res.text)
        if res.status_code == 200:
            try:
                data = res.json()
                logger.info("[META /me RAW JSON]: %s", data)
            except Exception:
                data = {}
            name = data.get("name")
            if name and str(name).strip():
                display_name = str(name).strip()
        else:
            try:
                err_data = res.json()
                logger.info("[META /me RAW JSON]: %s", err_data)
            except Exception:
                pass
    except Exception as e:
        logger.error("[META /me EXCEPTION]: %s", str(e), exc_info=True)
    try:
        acc_url = f"https://graph.facebook.com/v18.0/me/accounts?fields=id,name,access_token,instagram_business_account{{id,username,name}}&access_token={access_token}"
        logger.info("[META API CALL] Requesting %s", acc_url.replace(access_token, "HIDDEN_TOKEN"))
        res_acc = requests.get(acc_url, timeout=10)
        logger.info("[META /me/accounts STATUS]: %s | [BODY]: %s", res_acc.status_code, res_acc.text)
        if res_acc.status_code == 200:
            try:
                data = res_acc.json()
                logger.info("[META /me/accounts RAW JSON]: %s", data)
            except Exception:
                data = {}
            for page in data.get("data") or []:
                ig = page.get("instagram_business_account")
                if ig:
                    username = ig.get("username")
                    if username and str(username).strip():
                        return str(username).strip()
                    ig_name = ig.get("name")
                    if ig_name and str(ig_name).strip() and not display_name:
                        display_name = str(ig_name).strip()
                    if ig.get("id"):
                        try:
                            r2_url = f"https://graph.facebook.com/v18.0/{ig['id']}?fields=id,username,name&access_token={access_token}"
                            logger.info("[META API CALL] Requesting %s", r2_url.replace(access_token, "HIDDEN_TOKEN"))
                            r2 = requests.get(r2_url, timeout=10)
                            logger.info("[META /me STATUS]: %s | [BODY]: %s", r2.status_code, r2.text)
                            if r2.status_code == 200:
                                try:
                                    d2 = r2.json()
                                    logger.info("[META /me RAW JSON]: %s", d2)
                                except Exception:
                                    d2 = {}
                                username2 = d2.get("username") or d2.get("name")
                                if username2 and str(username2).strip():
                                    return str(username2).strip()
                        except Exception as e2:
                            logger.error("[META /me EXCEPTION]: %s", str(e2), exc_info=True)
                            continue
        else:
            try:
                err_data = res_acc.json()
                logger.info("[META /me/accounts RAW JSON]: %s", err_data)
            except Exception:
                pass
    except Exception as e:
        logger.error("[META /me/accounts EXCEPTION]: %s", str(e), exc_info=True)
    if display_name:
        return display_name
    logger.error("[INSTAGRAM API ERROR] No se pudo extraer username real de Meta")
    return "Instagram User"


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    short_data = exchange_code_for_short_lived_token(code)
    short_token = short_data.get("access_token")
    if not short_token:
        raise ValueError(f"Respuesta sin access_token short-lived: {short_data}")
    tokens: dict[str, Any]
    try:
        long_data = exchange_short_for_long_lived_token(short_token)
        long_token = long_data.get("access_token")
        if long_token:
            tokens = long_data
        else:
            tokens = short_data
    except Exception:
        tokens = short_data
    try:
        username = _fetch_instagram_username(tokens.get("access_token", ""))
        if username:
            tokens["username"] = username
    except Exception:
        pass
    return tokens


def save_instagram_tokens(db: Session, user_id: str, tokens: dict[str, Any]) -> SocialAccount:
    import uuid

    try:
        uid = uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ValueError(f"user_id inválido: {user_id}") from exc

    access_token = tokens.get("access_token")
    if not access_token:
        raise ValueError("tokens sin access_token")

    refresh_token = tokens.get("access_token")
    expires_in = tokens.get("expires_in")
    raw_username = tokens.get("username") or tokens.get("user_id")
    fetched_username: str | None = None
    if not raw_username:
        fetched_username = _fetch_instagram_username(access_token)
    username = str(raw_username or fetched_username or "").strip() or None
    if username:
        logger.info("[INSTAGRAM REAL USERNAME] Obtenido: %s", username)
    else:
        logger.error("[INSTAGRAM API ERROR] No se pudo extraer username real de Meta")
        username = None

    expires_at: datetime | None = None
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except Exception:
            expires_at = None
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(days=60)

    platform_account_id = str(tokens.get("user_id") or tokens.get("id") or uid)
    final_username = username or "Instagram User"
    platform_username = final_username
    platform_account_name = final_username
    logger.info("[INSTAGRAM DISPLAY NAME SAVED]: %s", final_username)
    logger.info("[FINAL INSTAGRAM USERNAME SAVED] %s", final_username)

    existing: SocialAccount | None = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "instagram")
    ).scalar_one_or_none()
    if existing is None:
        try:
            existing = db.query(SocialAccount).filter(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "instagram").first()
        except Exception:
            existing = None

    if existing is not None:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.token_expires_at = expires_at
        existing.platform_username = platform_username
        existing.platform_account_id = platform_account_id
        try:
            setattr(existing, "account_name", platform_account_name)
        except Exception:
            pass
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    account = SocialAccount(
        user_id=uid,
        platform="instagram",
        platform_account_id=platform_account_id,
        platform_username=platform_username,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=expires_at,
    )
    try:
        setattr(account, "account_name", platform_username)
    except Exception:
        pass
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


__all__ = [
    "get_instagram_auth_url",
    "exchange_code_for_short_lived_token",
    "exchange_short_for_long_lived_token",
    "exchange_code_for_tokens",
    "save_instagram_tokens",
    "_decode_state",
    "_encode_state",
]
