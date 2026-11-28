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
from .social_common import (
    decode_state as _decode_state,
    encode_state as _encode_state,
    require_access_token,
    validate_user_id,
)
from .token_crypto import cifrar_token



def _redirect_uri_temporal_youtube(redirect_uri: str) -> bool:
    """True si el URI aún apunta a un host temporal antiguo."""
    return (
        "decorator" in redirect_uri
        or "guns-camps" in redirect_uri
        or "ngrok" in redirect_uri
        or "trycloudflare" in redirect_uri
    )


def _redirect_uri_youtube() -> str:
    """URI de callback vigente (forzando el base público si es temporal)."""
    public_base = os.getenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz").strip().rstrip("/")
    default_uri = f"{public_base}/auth/social/youtube/callback"
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", default_uri).strip() or default_uri
    # Forzar api.clipsai.xyz si aún contiene URL temporal antigua
    if _redirect_uri_temporal_youtube(redirect_uri):
        return default_uri
    return redirect_uri


def _get_google_config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = _redirect_uri_youtube()
    return client_id, client_secret, redirect_uri



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


def _texto_no_vacio_youtube(valor: Any) -> bool:
    """True si el valor tiene texto no vacío al limpiarlo."""
    return bool(valor) and bool(str(valor).strip())


def _data_youtube(resp) -> Any:
    """JSON de la respuesta y log crudo; {} si falla o no es 200."""
    try:
        data = resp.json() if resp.status_code == 200 else {}
        logger.info("[YOUTUBE API] channels=%s", len(data.get("items", [])) if isinstance(data, dict) else 0)
    except Exception:
        data = {}
    return data


def _texto_de_snippet(snippet: dict, claves: tuple) -> str | None:
    """Primera clave del snippet con texto limpio."""
    for clave in claves:
        valor = snippet.get(clave)
        if _texto_no_vacio_youtube(valor):
            return str(valor).strip()
    return None


def _nombre_canal_youtube(data: Any) -> str | None:
    """customUrl/title del primer canal; None si no hay items."""
    items = data.get("items") or []
    if not items:
        return None
    snippet = items[0].get("snippet") or {}
    return _texto_de_snippet(snippet, ("customUrl", "title"))


def _log_error_canal(resp, data: Any) -> None:
    """Loguea el error estándar si no hay canal activo."""
    if resp.status_code != 200 or not (data.get("items") or []):
        logger.error("[YOUTUBE API ERROR] No se encontró canal activo")


def _fetch_youtube_username(access_token: str) -> str | None:
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        data = _data_youtube(resp)
        if resp.status_code == 200:
            nombre = _nombre_canal_youtube(data)
            if nombre is not None:
                return nombre
        _log_error_canal(resp, data)
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


def _expires_at_youtube(expires_in: Any) -> datetime | None:
    """Fecha de expiración del token; None si no se puede calcular."""
    if expires_in is None:
        return None
    try:
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    except Exception:
        return None


def _username_resuelto(raw_username: Any, fetched_username: str | None) -> str | None:
    """Username limpio entre el raw y el obtenido por API."""
    return str(raw_username or fetched_username or "").strip() or None


def _username_youtube(tokens: dict[str, Any], access_token: str) -> str | None:
    """Username real (raw o vía API) con su log de resultado."""
    raw_username = tokens.get("username")
    fetched_username: str | None = None
    if not raw_username:
        fetched_username = _fetch_youtube_username(access_token)
    username_real = _username_resuelto(raw_username, fetched_username)
    if username_real:
        logger.info("[YOUTUBE REAL USERNAME] Obtenido: %s", username_real)
    else:
        logger.error("[YOUTUBE API ERROR] No se encontró canal activo")
    return username_real


def _cuenta_existente_youtube(db: Session, uid: str) -> SocialAccount | None:
    """Cuenta YouTube existente del usuario vía select o query."""
    existing: SocialAccount | None = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "youtube")
    ).scalar_one_or_none()
    if existing is None:
        try:
            existing = db.query(SocialAccount).filter(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "youtube").first()
        except Exception:
            existing = None
    return existing


def _platform_account_id(tokens: dict[str, Any], uid: str) -> str:
    """Identificador de cuenta de plataforma del token o del uid."""
    return str(tokens.get("id") or tokens.get("user_id") or uid)


def _actualizar_cuenta_youtube(
    db: Session,
    existing: SocialAccount,
    access_token: str,
    refresh_token: Any,
    expires_at: datetime | None,
    username_real: str | None,
    platform_account_id: str,
    platform_username: str,
) -> SocialAccount:
    """Actualiza la cuenta YouTube existente y persiste cambios."""
    existing.access_token = cifrar_token(access_token)
    if refresh_token:
        existing.refresh_token = cifrar_token(refresh_token)
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


def _crear_cuenta_youtube(
    db: Session,
    uid: str,
    access_token: str,
    refresh_token: Any,
    expires_at: datetime | None,
    platform_account_id: str,
    platform_username: str,
) -> SocialAccount:
    """Crea y persiste una cuenta YouTube nueva."""
    if not refresh_token:
        refresh_token = access_token
    account = SocialAccount(
        user_id=uid,
        platform="youtube",
        platform_account_id=platform_account_id,
        platform_username=platform_username,
        access_token=cifrar_token(access_token),
        refresh_token=cifrar_token(refresh_token),
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


def save_youtube_tokens(db: Session, user_id: str, tokens: dict[str, Any]) -> SocialAccount:
    uid = validate_user_id(user_id)

    access_token = require_access_token(tokens)

    refresh_token = tokens.get("refresh_token")
    token_type = tokens.get("token_type", "Bearer")
    scope = tokens.get("scope", " ".join(YOUTUBE_SCOPES))
    expires_at = _expires_at_youtube(tokens.get("expires_in"))

    username_real = _username_youtube(tokens, access_token)

    existing = _cuenta_existente_youtube(db, uid)

    platform_account_id = _platform_account_id(tokens, uid)
    platform_username = username_real or ""

    if existing is not None:
        return _actualizar_cuenta_youtube(
            db, existing, access_token, refresh_token, expires_at,
            username_real, platform_account_id, platform_username,
        )
    return _crear_cuenta_youtube(
        db, uid, access_token, refresh_token, expires_at,
        platform_account_id, platform_username,
    )


__all__ = ["get_youtube_auth_url", "exchange_code_for_tokens", "save_youtube_tokens", "_decode_state", "_encode_state"]
