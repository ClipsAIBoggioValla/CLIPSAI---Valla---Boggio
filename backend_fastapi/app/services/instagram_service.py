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
    "business_management",
]

META_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
META_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
META_LONG_LIVED_URL = "https://graph.facebook.com/oauth/access_token"

DEFAULT_REDIRECT_URI = "https://api.clipsai.xyz/auth/social/instagram/callback"
from .social_common import (
    decode_state as _decode_state,
    encode_state as _encode_state,
    require_access_token,
    validate_user_id,
)
from .token_crypto import cifrar_token



def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return ""


_MARCAS_TUNEL_META = ("decorator", "guns-camps", "ngrok", "trycloudflare")


def _es_redirect_uri_tunel(redirect_uri: str) -> bool:
    """True si el redirect_uri apunta a un túnel temporal (ngrok/trycloudflare/etc)."""
    return any(marca in redirect_uri for marca in _MARCAS_TUNEL_META)


def _get_instagram_config() -> tuple[str, str, str]:
    client_id = _first_env("INSTAGRAM_CLIENT_ID", "META_APP_ID", "FB_CLIENT_ID")
    client_secret = _first_env("INSTAGRAM_CLIENT_SECRET", "META_APP_SECRET", "FB_CLIENT_SECRET")
    public_base = os.getenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz").strip().rstrip("/")
    default_uri = f"{public_base}/auth/social/instagram/callback"
    redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI", default_uri).strip() or default_uri
    if _es_redirect_uri_tunel(redirect_uri):
        redirect_uri = default_uri
    return client_id, client_secret, redirect_uri



def get_instagram_auth_url(user_id: str) -> str:
    client_id, _, redirect_uri = _get_instagram_config()
    if not client_id:
        raise ValueError("INSTAGRAM_CLIENT_ID / META_APP_ID no está configurado en el archivo .env del backend")
    state = _encode_state(str(user_id))
    # SCOPES requeridos para publicación de Reels y lectura de páginas
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(INSTAGRAM_SCOPES),
        "response_type": "code",
        "state": state or "",
        "auth_type": "rerequest",
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


def _json_seguro(res) -> dict:
    """JSON de la respuesta o {} si no es parseable."""
    try:
        return res.json()
    except Exception:
        return {}


def _logear_raw_json(res, prefijo: str) -> None:
    """Log del JSON crudo de la respuesta (silencioso si no es parseable)."""
    try:
        logger.info(f"{prefijo}: %s", res.json())
    except Exception:
        pass


def _nombre_de_respuesta_me(res) -> str | None:
    """Name del /me si la respuesta fue 200 con nombre válido."""
    if res.status_code != 200:
        _logear_raw_json(res, "[META /me RAW JSON]")
        return None
    data = _json_seguro(res)
    logger.info("[META /me RAW JSON]: %s", data)
    name = data.get("name")
    if name and str(name).strip():
        return str(name).strip()
    return None


def _nombre_desde_me(access_token: str) -> str | None:
    """Capa 1: GET /me → name. None si no hay nombre."""
    try:
        url = f"https://graph.facebook.com/v18.0/me?fields=id,name&access_token={access_token}"
        logger.info("[META API CALL] Requesting %s", url.replace(access_token, "HIDDEN_TOKEN"))
        res = requests.get(url, timeout=10)
        logger.info("[META /me STATUS]: %s | [BODY]: %s", res.status_code, res.text)
        return _nombre_de_respuesta_me(res)
    except Exception as e:
        logger.error("[META /me EXCEPTION]: %s", str(e), exc_info=True)
    return None


def _es_texto_valido(valor) -> bool:
    """True si el valor no es vacío tras strip."""
    return bool(valor) and bool(str(valor).strip())


def _display_name_de_pagina(ig: dict, display_name: str | None) -> str | None:
    """display_name actualizado con el name de la página si no se tenía uno."""
    ig_name = ig.get("name")
    if _es_texto_valido(ig_name) and not display_name:
        return str(ig_name).strip()
    return display_name


def _username_de_respuesta_ig(r2, display_name: str | None) -> tuple[str | None, str | None]:
    """(username, display_name) desde la respuesta /{ig_id} de la página."""
    d2 = _json_seguro(r2)
    logger.info("[META /me RAW JSON]: %s", d2)
    username2 = d2.get("username") or d2.get("name")
    if _es_texto_valido(username2):
        return str(username2).strip(), display_name
    return None, display_name


def _username_del_detalle_ig(ig_id, access_token: str, display_name: str | None) -> tuple[str | None, str | None]:
    """(username, display_name) consultando /{ig_id} de la página IG."""
    r2_url = f"https://graph.facebook.com/v18.0/{ig_id}?fields=id,username,name&access_token={access_token}"
    logger.info("[META API CALL] Requesting %s", r2_url.replace(access_token, "HIDDEN_TOKEN"))
    r2 = requests.get(r2_url, timeout=10)
    logger.info("[META /me STATUS]: %s | [BODY]: %s", r2.status_code, r2.text)
    return _username_de_respuesta_ig(r2, display_name)


def _username_de_pagina_ig(ig: dict, access_token: str, display_name: str | None) -> tuple[str | None, str | None]:
    """Extrae username de una página IG (directo, o consulta /{ig_id}). Devuelve (username, display_name)."""
    username = ig.get("username")
    if _es_texto_valido(username):
        return str(username).strip(), display_name
    display_name = _display_name_de_pagina(ig, display_name)
    if not ig.get("id"):
        return None, display_name
    try:
        return _username_del_detalle_ig(ig["id"], access_token, display_name)
    except Exception as e2:
        logger.error("[META /me EXCEPTION]: %s", str(e2), exc_info=True)
    return None, display_name


def _paginas_de_accounts(data: dict) -> list:
    """Lista de páginas del /me/accounts (vacía si no hay)."""
    return data.get("data") or []


def _username_de_paginas(data: dict, access_token: str, display_name: str | None) -> tuple[str | None, str | None]:
    """(username, display_name) recorriendo las páginas del /me/accounts."""
    for page in _paginas_de_accounts(data):
        ig = page.get("instagram_business_account")
        if ig:
            username, display_name = _username_de_pagina_ig(ig, access_token, display_name)
            if username:
                return username, display_name
    return None, display_name


def _username_desde_accounts(access_token: str, display_name: str | None) -> tuple[str | None, str | None]:
    """Capa 2: GET /me/accounts → instagram_business_account de cada página."""
    try:
        acc_url = f"https://graph.facebook.com/v18.0/me/accounts?fields=id,name,access_token,instagram_business_account{{id,username,name}}&access_token={access_token}"
        logger.info("[META API CALL] Requesting %s", acc_url.replace(access_token, "HIDDEN_TOKEN"))
        res_acc = requests.get(acc_url, timeout=10)
        logger.info("[META /me/accounts STATUS]: %s | [BODY]: %s", res_acc.status_code, res_acc.text)
        if res_acc.status_code != 200:
            _logear_raw_json(res_acc, "[META /me/accounts RAW JSON]")
            return None, display_name
        data = _json_seguro(res_acc)
        logger.info("[META /me/accounts RAW JSON]: %s", data)
        return _username_de_paginas(data, access_token, display_name)
    except Exception as e:
        logger.error("[META /me/accounts EXCEPTION]: %s", str(e), exc_info=True)
    return None, display_name


def _fetch_instagram_username(access_token: str) -> str | None:
    display_name = _nombre_desde_me(access_token)
    username, display_name = _username_desde_accounts(access_token, display_name)
    if username:
        return username
    if display_name:
        return display_name
    logger.error("[INSTAGRAM API ERROR] No se pudo extraer username real de Meta")
    return "Instagram User"


def _tokens_largos_o_cortos(short_data: dict) -> dict:
    """Tokens long-lived si el exchange funcionó; si no, los short-lived."""
    try:
        long_data = exchange_short_for_long_lived_token(short_data.get("access_token"))
        if long_data.get("access_token"):
            return long_data
    except Exception:
        pass
    return short_data


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    short_data = exchange_code_for_short_lived_token(code)
    short_token = short_data.get("access_token")
    if not short_token:
        raise ValueError(f"Respuesta sin access_token short-lived: {short_data}")
    tokens: dict[str, Any] = _tokens_largos_o_cortos(short_data)
    try:
        username = _fetch_instagram_username(tokens.get("access_token", ""))
        if username:
            tokens["username"] = username
    except Exception:
        pass
    return tokens


def _raw_username_de_tokens(tokens: dict) -> str | None:
    """Username crudo del payload de tokens (username o user_id)."""
    return tokens.get("username") or tokens.get("user_id")


def _normalizar_username(raw) -> str | None:
    """Username limpio no vacío; None si no aplica."""
    return str(raw or "").strip() or None


def _resolver_username(tokens: dict, access_token: str) -> str | None:
    """Username real a guardar (tokens o fetch en Meta); None si no se pudo."""
    raw_username = _raw_username_de_tokens(tokens)
    if not raw_username:
        raw_username = _fetch_instagram_username(access_token)
    username = _normalizar_username(raw_username)
    if username:
        logger.info("[INSTAGRAM REAL USERNAME] Obtenido: %s", username)
    else:
        logger.error("[INSTAGRAM API ERROR] No se pudo extraer username real de Meta")
        username = None
    return username


def _expires_at_de_tokens(tokens: dict) -> datetime | None:
    """Fecha de expiración del token (60 días por defecto)."""
    expires_in = tokens.get("expires_in")
    if expires_in is None:
        return datetime.now(timezone.utc) + timedelta(days=60)
    try:
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    except Exception:
        return None


def _credenciales_debug_validas() -> tuple[str, str] | None:
    """(client_id, client_secret) para debug_token de Meta; None si faltan."""
    dbg_client_id, dbg_client_secret, _ = _get_instagram_config()
    if dbg_client_id and dbg_client_secret:
        return dbg_client_id, dbg_client_secret
    return None


def _pedir_debug_token(access_token: str, app_token: str):
    """Respuesta de debug_token de Meta (con log de status)."""
    dbg_url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={app_token}"
    dbg_resp = requests.get(dbg_url, timeout=10)
    logger.info("[IG DEBUG] debug_token status=%s body=%s", dbg_resp.status_code, dbg_resp.text)
    return dbg_resp


def _logear_scopes_de_respuesta(dbg_resp) -> None:
    """Log de los scopes concedidos de la respuesta de debug_token (silencioso si falla)."""
    try:
        dbg_data = dbg_resp.json()
        scopes = dbg_data.get("data", {}).get("scopes", [])
        logger.info("[IG DEBUG] scopes concedidos: %s", scopes)
    except Exception:
        pass


def _logear_scopes_debug(access_token: str) -> None:
    """DEBUG: registra los scopes concedidos del token (silencioso si falla)."""
    try:
        _debug_y_logear_scopes(access_token)
    except Exception as e:
        logger.warning(f"[IG DEBUG] debug_token failed: {e}")


def _debug_y_logear_scopes(access_token: str) -> None:
    """GET debug_token y log de los scopes concedidos si la respuesta es 200."""
    creds = _credenciales_debug_validas()
    if creds and access_token:
        app_token = f"{creds[0]}|{creds[1]}"
        dbg_resp = _pedir_debug_token(access_token, app_token)
        if dbg_resp.status_code == 200:
            _logear_scopes_de_respuesta(dbg_resp)


def _cuenta_existente_ig(db: Session, uid) -> SocialAccount | None:
    """Cuenta instagram existente del usuario (ORM select con fallback db.query)."""
    existing: SocialAccount | None = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "instagram")
    ).scalar_one_or_none()
    if existing is None:
        try:
            existing = db.query(SocialAccount).filter(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "instagram").first()
        except Exception:
            existing = None
    return existing


def _actualizar_cuenta_ig(db: Session, existing: SocialAccount, access_token, refresh_token, expires_at, platform_account_id, final_username) -> None:
    """Actualiza la cuenta IG existente con los nuevos tokens."""
    existing.access_token = cifrar_token(access_token)
    existing.refresh_token = cifrar_token(refresh_token)
    existing.token_expires_at = expires_at
    existing.platform_username = final_username
    existing.platform_account_id = platform_account_id
    try:
        setattr(existing, "account_name", final_username)
    except Exception:
        pass
    existing.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(existing)


def _cuenta_nueva_ig(db: Session, uid, access_token, refresh_token, expires_at, platform_account_id, final_username) -> SocialAccount:
    """Crea y persiste la cuenta IG nueva."""
    account = SocialAccount(
        user_id=uid,
        platform="instagram",
        platform_account_id=platform_account_id,
        platform_username=final_username,
        access_token=cifrar_token(access_token),
        refresh_token=cifrar_token(refresh_token),
        token_expires_at=expires_at,
    )
    try:
        setattr(account, "account_name", final_username)
    except Exception:
        pass
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _platform_account_id_ig(tokens: dict, uid) -> str:
    """Identificador de cuenta IG del payload (user_id, id o uid)."""
    return str(tokens.get("user_id") or tokens.get("id") or uid)


def save_instagram_tokens(db: Session, user_id: str, tokens: dict[str, Any]) -> SocialAccount:
    uid = validate_user_id(user_id)

    access_token = require_access_token(tokens)

    refresh_token = tokens.get("access_token")
    username = _resolver_username(tokens, access_token)
    expires_at = _expires_at_de_tokens(tokens)

    platform_account_id = _platform_account_id_ig(tokens, uid)
    final_username = username or "Instagram User"
    logger.info("[INSTAGRAM DISPLAY NAME SAVED]: %s", final_username)
    logger.info("[FINAL INSTAGRAM USERNAME SAVED] %s", final_username)

    # DEBUG: verificar scopes concedidos antes de guardar token
    _logear_scopes_debug(access_token)

    existing = _cuenta_existente_ig(db, uid)
    if existing is not None:
        _actualizar_cuenta_ig(db, existing, access_token, refresh_token, expires_at, platform_account_id, final_username)
        return existing

    return _cuenta_nueva_ig(db, uid, access_token, refresh_token, expires_at, platform_account_id, final_username)


__all__ = [
    "get_instagram_auth_url",
    "exchange_code_for_short_lived_token",
    "exchange_short_for_long_lived_token",
    "exchange_code_for_tokens",
    "save_instagram_tokens",
    "_decode_state",
    "_encode_state",
]
