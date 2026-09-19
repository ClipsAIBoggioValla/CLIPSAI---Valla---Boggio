from __future__ import annotations

import base64
import json
import logging
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import SocialAccount

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

DEFAULT_REDIRECT_URI = "https://api.clipsai.xyz/auth/social/youtube/callback"


def _get_google_config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    # Usa PUBLIC_BACKEND_URL como base si GOOGLE_REDIRECT_URI no está configurado o es temporal
    public_base = os.getenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz").strip().rstrip("/")
    default_uri = f"{public_base}/auth/social/youtube/callback"
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", default_uri).strip() or default_uri
    # Forzar api.clipsai.xyz si aún contiene URL temporal antigua
    if "decorator" in redirect_uri or "guns-camps" in redirect_uri or "ngrok" in redirect_uri or "trycloudflare" in redirect_uri:
        redirect_uri = default_uri
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


def get_youtube_auth_url(user_id: str) -> str:
    client_id, _, redirect_uri = _get_google_config()
    state = _encode_state(str(user_id))
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _fetch_youtube_username(access_token: str) -> str | None:
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        try:
            data = resp.json() if resp.status_code == 200 else {}
            logger.info("[YOUTUBE API RAW RESPONSE] Channels: %s", data)
        except Exception:
            data = {}
        if resp.status_code == 200:
            items = data.get("items") or []
            if items:
                snippet = items[0].get("snippet") or {}
                custom = snippet.get("customUrl")
                if custom and str(custom).strip():
                    return str(custom).strip()
                title = snippet.get("title")
                if title and str(title).strip():
                    return str(title).strip()
        if resp.status_code != 200 or not (data.get("items") or []):
            logger.error("[YOUTUBE API ERROR] No se encontró canal activo")
    except Exception as e:
        logger.error("[YOUTUBE API ERROR] No se encontró canal activo: %s", str(e))
    return None


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    client_id, client_secret, redirect_uri = _get_google_config()
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()
    try:
        username = _fetch_youtube_username(tokens.get("access_token", ""))
        if username:
            tokens["username"] = username
            logger.info("[YOUTUBE REAL USERNAME] Obtenido: %s", username)
    except Exception:
        pass
    return tokens


def save_youtube_tokens(db: Session, user_id: str, tokens: dict[str, Any]) -> SocialAccount:
    import uuid

    try:
        uid = uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ValueError(f"user_id inválido: {user_id}") from exc

    access_token = tokens.get("access_token")
    if not access_token:
        raise ValueError("tokens sin access_token")

    refresh_token = tokens.get("refresh_token")
    token_type = tokens.get("token_type", "Bearer")
    scope = tokens.get("scope", " ".join(YOUTUBE_SCOPES))
    expires_in = tokens.get("expires_in")

    expires_at: datetime | None = None
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except Exception:
            expires_at = None

    raw_username = tokens.get("username")
    fetched_username: str | None = None
    if not raw_username:
        fetched_username = _fetch_youtube_username(access_token)
    username_real = str(raw_username or fetched_username or "").strip() or None
    if username_real:
        logger.info("[YOUTUBE REAL USERNAME] Obtenido: %s", username_real)
    else:
        logger.error("[YOUTUBE API ERROR] No se encontró canal activo")

    existing: SocialAccount | None = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "youtube")
    ).scalar_one_or_none()
    if existing is None:
        try:
            existing = db.query(SocialAccount).filter(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "youtube").first()
        except Exception:
            existing = None

    platform_account_id = str(tokens.get("id") or tokens.get("user_id") or uid)
    platform_username = username_real or ""

    if existing is not None:
        existing.access_token = access_token
        if refresh_token:
            existing.refresh_token = refresh_token
        existing.token_expires_at = expires_at
        if username_real:
            existing.platform_username = platform_username
            try:
                setattr(existing, "account_name", platform_username)
            except Exception:
                pass
            existing.platform_account_id = platform_account_id
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    if not refresh_token:
        refresh_token = access_token

    account = SocialAccount(
        user_id=uid,
        platform="youtube",
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


__all__ = ["get_youtube_auth_url", "exchange_code_for_tokens", "save_youtube_tokens", "_decode_state", "_encode_state"]
