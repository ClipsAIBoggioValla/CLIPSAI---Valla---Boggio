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
from .social_common import (
    decode_state as _decode_state,
    encode_state as _encode_state,
    validate_user_id,
)



def _limpio_si_presente(valor: str) -> str:
    """Cadena limpia del valor; '' si es falsy."""
    return (valor or "").strip() if valor else ""


def _env_o_global(env_name: str, global_value: str) -> str:
    """Valor limpio de la variable de entorno o del global capturado al importar."""
    valor = os.getenv(env_name, "").strip() if os.getenv(env_name) else ""
    if not valor:
        valor = _limpio_si_presente(global_value)
    return valor


def _redirect_uri_descartable(redirect_uri: str) -> bool:
    """True si el URI apunta a un host de desarrollo no permitido."""
    return (
        "decorator" in redirect_uri
        or "guns-camps" in redirect_uri
        or "ngrok" in redirect_uri
        or "trycloudflare" in redirect_uri
    )


def _redirect_uri_tiktok() -> str:
    """URI de callback vigente (sin hosts de desarrollo)."""
    public_base = os.getenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz").strip().rstrip("/")
    default_uri = f"{public_base}/auth/social/tiktok/callback"
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", default_uri).strip() or default_uri
    if _redirect_uri_descartable(redirect_uri):
        return default_uri
    return redirect_uri


def _get_tiktok_config() -> tuple[str, str, str]:
    """(client_key, client_secret, redirect_uri) de entorno o globals."""
    client_key = _env_o_global("TIKTOK_CLIENT_KEY", TIKTOK_CLIENT_KEY)
    client_secret = _env_o_global("TIKTOK_CLIENT_SECRET", TIKTOK_CLIENT_SECRET)
    redirect_uri = _redirect_uri_tiktok()
    return client_key, client_secret, redirect_uri



def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def get_tiktok_auth_url(state: str, code_challenge: str) -> str:
    client_key, _client_secret, redirect_uri = _get_tiktok_config()
    if not client_key:
        raise ValueError("[TIKTOK ERROR] TIKTOK_CLIENT_KEY no está configurada en las variables de entorno.")
    params = {
        "client_key": client_key,
        "scope": TIKTOK_SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
    logger.info("[TIKTOK AUTH URL GENERATED]: %s", auth_url.replace(client_key, "HIDDEN_KEY"))
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


def _json_seguro(resp) -> Any:
    """JSON de la respuesta; {} si no es parseable."""
    try:
        return resp.json()
    except Exception:
        return {}


def _texto_no_vacio(valor: Any) -> bool:
    """True si el valor tiene texto no vacío al limpiarlo."""
    return bool(valor) and bool(str(valor).strip())


def _user_de_data(data: dict) -> Any:
    """Usuario dentro de data.data o data.user; data si no hay ninguno."""
    if "data" in data and isinstance(data["data"], dict):
        return data["data"].get("user")
    if "user" in data:
        return data.get("user")
    return data


def _user_de_respuesta(data: Any) -> Any:
    """Extrae el dict de usuario de la respuesta de TikTok."""
    if not isinstance(data, dict):
        return None
    return _user_de_data(data)


def _identificador_de_user(user: Any) -> str | None:
    """display_name u open_id del usuario, limpio; None si no hay."""
    if not isinstance(user, dict):
        return None
    display_name = user.get("display_name")
    if _texto_no_vacio(display_name):
        return str(display_name).strip()
    open_id = user.get("open_id")
    if _texto_no_vacio(open_id):
        return str(open_id).strip()
    return None


def _fallback_data(data: Any) -> Any:
    """data.data.user como último recurso."""
    d = data.get("data") or {}
    return d.get("user") or {}


def _identificador_de_data(data: Any) -> str | None:
    """display_name u open_id desde data.data.user como último recurso."""
    if not isinstance(data, dict):
        return None
    u = _fallback_data(data)
    dn = u.get("display_name") or u.get("open_id")
    if _texto_no_vacio(dn):
        return str(dn).strip()
    return None


def _fetch_tiktok_user_info(access_token: str) -> str:
    try:
        url = f"{TIKTOK_USER_INFO_URL}?fields=open_id,union_id,avatar_url,display_name"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        logger.info("[TIKTOK USER INFO RAW RESPONSE]: %s", resp.text)
        if resp.status_code == 200:
            data = _json_seguro(resp)
            nombre = _identificador_de_user(_user_de_respuesta(data))
            if nombre is None:
                nombre = _identificador_de_data(data)
            if nombre is not None:
                return nombre
    except Exception as e:
        logger.error("[TIKTOK USER INFO ERROR]: %s", str(e), exc_info=True)
    return "TikTok User"


def _access_token_de_tokens(token_data: dict[str, Any]) -> str:
    """access_token como string; ValueError si falta."""
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("tokens sin access_token")
    return str(access_token)


def _open_id_directo(token_data: dict[str, Any]) -> str | None:
    """open_id del formato condicional original (None si data no es dict)."""
    if isinstance(token_data.get("data"), dict):
        return (
            token_data.get("open_id")
            or token_data.get("open_id,")
            or token_data["data"].get("open_id")
        )
    return None


def _open_id_del_nested(token_data: dict[str, Any]) -> str | None:
    """open_id del payload anidado (data o el propio token_data)."""
    try:
        d = token_data.get("data") if isinstance(token_data.get("data"), dict) else token_data
        if isinstance(d, dict):
            return d.get("open_id")
    except Exception:
        pass
    return None


def _open_id_de_tokens(token_data: dict[str, Any], uid: str) -> str:
    """open_id resuelto; str(uid) como último recurso."""
    open_id = _open_id_directo(token_data)
    if not open_id:
        open_id = _open_id_del_nested(token_data)
    if not open_id:
        open_id = str(uid)
    return open_id


def _expires_at_de_tokens(expires_in: Any) -> datetime | None:
    """Fecha de expiración del token; None si no se puede calcular."""
    if expires_in is None:
        return None
    try:
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    except Exception:
        return None


def _display_name_tiktok(access_token: str) -> str:
    """Nombre visible del usuario TikTok, con fallback estándar."""
    display_name = _fetch_tiktok_user_info(access_token)
    if not display_name or not str(display_name).strip():
        display_name = "TikTok User"
    return str(display_name).strip()


def _cuenta_existente_tiktok(db: Session, uid: str) -> SocialAccount | None:
    """Cuenta TikTok existente del usuario vía select o query."""
    existing: SocialAccount | None = db.execute(
        select(SocialAccount).where(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "tiktok")
    ).scalar_one_or_none()
    if existing is None:
        try:
            existing = db.query(SocialAccount).filter(SocialAccount.user_id == uid, func.lower(SocialAccount.platform) == "tiktok").first()
        except Exception:
            existing = None
    return existing


def _actualizar_cuenta(
    db: Session,
    existing: SocialAccount,
    access_token: str,
    refresh_token: str,
    expires_at: datetime | None,
    open_id: str,
    display_name: str,
) -> SocialAccount:
    """Actualiza la cuenta existente y persiste cambios."""
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


def _crear_cuenta_tiktok(
    db: Session,
    uid: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime | None,
    open_id: str,
    display_name: str,
) -> SocialAccount:
    """Crea y persiste una cuenta TikTok nueva."""
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


def save_tiktok_tokens(db: Session, user_id: str, token_data: dict[str, Any]) -> SocialAccount:
    uid = validate_user_id(user_id)

    access_token = _access_token_de_tokens(token_data)
    refresh_token = token_data.get("refresh_token") or access_token
    open_id = _open_id_de_tokens(token_data, uid)
    expires_at = _expires_at_de_tokens(token_data.get("expires_in"))
    display_name = _display_name_tiktok(access_token)

    existing = _cuenta_existente_tiktok(db, uid)
    if existing is not None:
        return _actualizar_cuenta(
            db, existing, access_token, refresh_token, expires_at, open_id, display_name
        )
    return _crear_cuenta_tiktok(
        db, uid, access_token, refresh_token, expires_at, open_id, display_name
    )


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
