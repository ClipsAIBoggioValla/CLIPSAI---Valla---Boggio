from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import SocialAccount

logger = logging.getLogger(__name__)

# === TikTok API v2 - FILE_UPLOAD 100% real ===
# Servicio utiliza API v2: https://open.tiktokapis.com/v2/post/publish/video/init/
# Requiere archivo físico real en storage_path (sin fallback de prueba)

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
TIKTOK_PUBLISH_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

DEFAULT_REDIRECT_URI = "https://api.clipsai.xyz/auth/social/tiktok/callback"

raw_scopes = os.getenv("TIKTOK_SCOPES", "user.info.basic,video.upload,video.publish")
_scopes_list = [s.strip() for s in raw_scopes.split(",") if s.strip()]
# Asegurar los tres scopes obligatorios separados por coma
for _req in ["user.info.basic", "video.upload", "video.publish"]:
    if _req not in _scopes_list:
        _scopes_list.append(_req)
TIKTOK_SCOPES = ",".join(_scopes_list)

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "").strip()


def _get_tiktok_config() -> tuple[str, str, str]:
    client_key = os.getenv("TIKTOK_CLIENT_KEY", "").strip() if os.getenv("TIKTOK_CLIENT_KEY") else ""
    if not client_key:
        client_key = (TIKTOK_CLIENT_KEY or "").strip() if TIKTOK_CLIENT_KEY else ""
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip() if os.getenv("TIKTOK_CLIENT_SECRET") else ""
    if not client_secret:
        client_secret = (TIKTOK_CLIENT_SECRET or "").strip() if TIKTOK_CLIENT_SECRET else ""
    public_base = os.getenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz").strip().rstrip("/")
    default_uri = f"{public_base}/auth/social/tiktok/callback"
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", default_uri).strip() or default_uri
    if "decorator" in redirect_uri or "guns-camps" in redirect_uri or "ngrok" in redirect_uri or "trycloudflare" in redirect_uri:
        redirect_uri = default_uri
    return client_key, client_secret, redirect_uri


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


def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def get_tiktok_auth_url(state: str, code_challenge: str) -> str:
    if not TIKTOK_CLIENT_KEY:
        raise ValueError("[TIKTOK ERROR] TIKTOK_CLIENT_KEY no está configurada en las variables de entorno.")
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": TIKTOK_SCOPES,
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
    logger.info("[TIKTOK AUTH URL GENERATED]: %s", auth_url.replace(TIKTOK_CLIENT_KEY, "HIDDEN_KEY"))
    return auth_url


def get_tiktok_auth_url_for_user(user_id: str) -> str:
    verifier, challenge = generate_pkce_pair()
    state_data = {"user_id": str(user_id), "code_verifier": verifier}
    state = base64.urlsafe_b64encode(json.dumps(state_data, separators=(",", ":")).encode()).decode().rstrip("=")
    return get_tiktok_auth_url(state, challenge)


def exchange_tiktok_code(code: str, code_verifier: str) -> dict[str, Any]:
    client_key, client_secret, redirect_uri = _get_tiktok_config()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    resp = requests.post(TIKTOK_TOKEN_URL, headers=headers, data=data, timeout=15)
    logger.info("[TIKTOK TOKEN RAW RESPONSE]: %s", resp.text)
    resp.raise_for_status()
    try:
        token_data = resp.json()
    except Exception:
        token_data = {}
    return token_data


def _fetch_tiktok_user_info(access_token: str) -> str:
    try:
        url = f"{TIKTOK_USER_INFO_URL}?fields=open_id,union_id,avatar_url,display_name"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        logger.info("[TIKTOK USER INFO RAW RESPONSE]: %s", resp.text)
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = {}
            user = None
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], dict):
                    user = data["data"].get("user")
                elif "user" in data:
                    user = data.get("user")
                else:
                    user = data
            if isinstance(user, dict):
                display_name = user.get("display_name")
                if display_name and str(display_name).strip():
                    return str(display_name).strip()
                open_id = user.get("open_id")
                if open_id and str(open_id).strip():
                    return str(open_id).strip()
            if isinstance(data, dict):
                d = data.get("data") or {}
                u = d.get("user") or {}
                dn = u.get("display_name") or u.get("open_id")
                if dn and str(dn).strip():
                    return str(dn).strip()
    except Exception as e:
        logger.error("[TIKTOK USER INFO ERROR]: %s", str(e), exc_info=True)
    return "TikTok User"


def save_tiktok_tokens(db: Session, user_id: str, token_data: dict[str, Any]) -> SocialAccount:
    import uuid

    try:
        uid = uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ValueError(f"user_id inválido: {user_id}") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("tokens sin access_token")

    refresh_token = token_data.get("refresh_token") or access_token
    expires_in = token_data.get("expires_in")
    open_id = token_data.get("open_id") or token_data.get("open_id,") or token_data.get("data", {}).get("open_id") if isinstance(token_data.get("data"), dict) else None
    if not open_id:
        try:
            d = token_data.get("data") if isinstance(token_data.get("data"), dict) else token_data
            if isinstance(d, dict):
                open_id = d.get("open_id")
        except Exception:
            pass
    if not open_id:
        open_id = str(uid)

    expires_at: datetime | None = None
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except Exception:
            expires_at = None

    display_name = _fetch_tiktok_user_info(access_token)
    if not display_name or not str(display_name).strip():
        display_name = "TikTok User"
    display_name = str(display_name).strip()

    existing: SocialAccount | None = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "tiktok")
    ).scalar_one_or_none()
    if existing is None:
        try:
            existing = db.query(SocialAccount).filter(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "tiktok").first()
        except Exception:
            existing = None

    if existing is not None:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.token_expires_at = expires_at
        existing.platform_account_id = str(open_id)
        existing.platform_username = display_name
        try:
            setattr(existing, "account_name", display_name)
        except Exception:
            pass
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        logger.info("[TIKTOK USER SAVED]: %s", display_name)
        return existing

    account = SocialAccount(
        user_id=uid,
        platform="tiktok",
        platform_account_id=str(open_id),
        platform_username=display_name,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=expires_at,
    )
    try:
        setattr(account, "account_name", display_name)
    except Exception:
        pass
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info("[TIKTOK USER SAVED]: %s", display_name)
    return account


__all__ = [
    "generate_pkce_pair",
    "get_tiktok_auth_url",
    "get_tiktok_auth_url_for_user",
    "exchange_tiktok_code",
    "_fetch_tiktok_user_info",
    "save_tiktok_tokens",
    "_decode_state",
    "_encode_state",
]
