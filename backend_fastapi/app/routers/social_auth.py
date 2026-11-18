from __future__ import annotations

import logging
import os
import urllib.parse

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func

from ..deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)
from ..services.youtube_service import (
    exchange_code_for_tokens as yt_exchange_code_for_tokens,
)
from ..services.youtube_service import get_youtube_auth_url as yt_get_youtube_auth_url
from ..services.youtube_service import save_youtube_tokens as yt_save_youtube_tokens
from ..services.youtube_service import _decode_state as yt_decode_state

try:
    from ..services.instagram_service import (
        exchange_code_for_tokens as ig_exchange_code_for_tokens,
    )
    from ..services.instagram_service import get_instagram_auth_url as ig_get_instagram_auth_url
    from ..services.instagram_service import save_instagram_tokens as ig_save_instagram_tokens
    from ..services.instagram_service import _decode_state as ig_decode_state
except Exception:  # pragma: no cover
    ig_get_instagram_auth_url = None  # type: ignore
    ig_exchange_code_for_tokens = None  # type: ignore
    ig_save_instagram_tokens = None  # type: ignore
    ig_decode_state = yt_decode_state  # type: ignore

try:
    from ..services.tiktok_service import exchange_tiktok_code as tt_exchange_tiktok_code
    from ..services.tiktok_service import generate_pkce_pair as tt_generate_pkce_pair
    from ..services.tiktok_service import get_tiktok_auth_url as tt_get_tiktok_auth_url
    from ..services.tiktok_service import save_tiktok_tokens as tt_save_tiktok_tokens
    from ..services.tiktok_service import _decode_state as tt_decode_state
    from ..services.tiktok_service import _encode_state as tt_encode_state
except Exception:  # pragma: no cover
    tt_get_tiktok_auth_url = None  # type: ignore
    tt_generate_pkce_pair = None  # type: ignore
    tt_exchange_tiktok_code = None  # type: ignore
    tt_save_tiktok_tokens = None  # type: ignore
    tt_decode_state = yt_decode_state  # type: ignore
    tt_encode_state = None  # type: ignore

router = APIRouter(tags=["Social Auth"])


def _logear_cuentas_encontradas(accounts, user_id) -> None:
    """Log de las cuentas encontradas en BD con sus usernames."""
    logger.info("Cuentas encontradas en BD: %s", [(a.platform, getattr(a, "platform_username", None) or getattr(a, "account_name", None)) for a in accounts])


def _es_username_fallback(raw_username) -> bool:
    """True si el username es un fallback sintético plataforma_XXXXXXXX (o está vacío)."""
    import re

    fallback_re = re.compile(r"^(instagram|youtube|tiktok)_[0-9a-fA-F]{8}$")
    if not raw_username or not str(raw_username).strip():
        return True
    return bool(fallback_re.match(str(raw_username).strip()))


def _username_real(acc) -> str | None:
    """Username real de la cuenta (None si es un fallback sintético o vacío)."""
    raw_username = getattr(acc, "platform_username", None) or getattr(acc, "account_name", None)
    if not _es_username_fallback(raw_username):
        return raw_username
    return None


def _username_visible(platform: str, username_val: str | None) -> str | None:
    """Username de muestra por plataforma si no se resolvió uno real."""
    if username_val:
        return username_val
    if platform == "instagram":
        return "Instagram User"
    if platform == "tiktok":
        return "TikTok User"
    return None


def _estado_de_cuenta(acc, user_id) -> dict:
    """Entrada de status para una cuenta conectada."""
    logger.info("[STATUS DEBUG] User %s - %s DB Username: %s", user_id, acc.platform, acc.platform_username)
    platform = (acc.platform or "").lower()
    return {
        "connected": True,
        "username": _username_visible(platform, _username_real(acc)),
        "expires_at": acc.token_expires_at.isoformat() if getattr(acc, "token_expires_at", None) else None,
    }


def _plataforma_configurada(platform: str) -> bool:
    """True si las credenciales de OAuth de la plataforma están en el entorno."""
    import os as _os

    env = _os.getenv
    if platform == "youtube":
        return bool((env("GOOGLE_CLIENT_ID") or "").strip()) and bool((env("GOOGLE_CLIENT_SECRET") or "").strip())
    if platform == "instagram":
        return bool((env("INSTAGRAM_CLIENT_ID") or env("META_APP_ID") or env("FB_CLIENT_ID") or "").strip())
    if platform == "tiktok":
        return bool((env("TIKTOK_CLIENT_KEY") or "").strip()) and bool((env("TIKTOK_CLIENT_SECRET") or "").strip())
    return False


def _estado_default(platform: str) -> dict:
    """Entrada base de la plataforma: desconectada + flag de configuración del servidor."""
    return {"connected": False, "username": None, "expires_at": None, "configured": _plataforma_configurada(platform)}


@router.get("/status", summary="Estado de integraciones conectadas")
@router.get("/accounts", summary="Estado de integraciones conectadas (alias)", include_in_schema=False)
async def get_social_status(
    current_user: CurrentUser,
    db: DbSession,
):
    from ..models import SocialAccount

    logger.info("Consulta /status para user_id: %s (tipo: %s)", current_user.id, type(current_user.id))
    accounts = db.query(SocialAccount).filter(SocialAccount.user_id == current_user.id).all()
    _logear_cuentas_encontradas(accounts, current_user.id)

    status = {
        "instagram": _estado_default("instagram"),
        "youtube": _estado_default("youtube"),
        "tiktok": _estado_default("tiktok"),
    }

    for acc in accounts:
        platform = (acc.platform or "").lower()
        if platform in status:
            entrada = _estado_de_cuenta(acc, current_user.id)
            entrada["configured"] = status[platform]["configured"]
            status[platform] = entrada

    return status





def _get_frontend_base() -> str:
    base = os.getenv("FRONTEND_REDIRECT_URL", "").strip()
    if not base:
        base = os.getenv("FRONTEND_URL", "").strip()
    if not base:
        base = "http://localhost:3000"
    return base.rstrip("/")


def _cuenta_social(db, user_id, platform_norm: str):
    """Cuenta social del usuario para la plataforma (None si falla la query)."""
    from ..models import SocialAccount

    try:
        return db.query(SocialAccount).filter(
            SocialAccount.user_id == user_id,
            func.lower(SocialAccount.platform) == platform_norm,
        ).first()
    except Exception:
        return None


def _desconectar_legacy(db, user_id, platform_norm: str) -> bool:
    """Elimina la fila de la tabla legacy user_social_accounts; True si lo hizo."""
    try:
        from sqlalchemy import text

        row = db.execute(
            text("SELECT id FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat LIMIT 1"),
            {"uid": str(user_id), "plat": platform_norm},
        ).mappings().first()
        if row:
            db.execute(
                text("DELETE FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat"),
                {"uid": str(user_id), "plat": platform_norm},
            )
            db.commit()
            return True
    except Exception:
        pass
    return False


def _eliminar_cuenta_orm(db, account, user_id, platform_norm: str) -> None:
    """Elimina la cuenta por ORM con fallback SQL crudo; HTTPException 500 si ambos fallan."""
    from fastapi import HTTPException

    try:
        db.delete(account)
        db.commit()
    except Exception:
        try:
            from sqlalchemy import text

            db.execute(
                text("DELETE FROM social_accounts WHERE user_id = :uid AND lower(platform) = :plat"),
                {"uid": str(user_id), "plat": platform_norm},
            )
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))


def _limpiar_tabla_legacy(db, user_id, platform_norm: str) -> None:
    """Limpieza adicional en tabla legacy si existe (silenciosa)."""
    try:
        from sqlalchemy import text

        db.execute(
            text("DELETE FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat"),
            {"uid": str(user_id), "plat": platform_norm},
        )
        db.commit()
    except Exception:
        pass


@router.delete("/{platform}", summary="Desconectar cuenta social")
def disconnect_social(
    platform: str,
    current_user: CurrentUser,
    db: DbSession,
):
    from fastapi import HTTPException

    platform_norm = platform.strip().lower()
    allowed = {"tiktok", "youtube", "instagram"}
    if platform_norm not in allowed:
        raise HTTPException(status_code=400, detail=f"Plataforma no válida: {platform}")

    # Elimina fila correspondiente en user_social_accounts / social_accounts
    account = _cuenta_social(db, current_user.id, platform_norm)

    if account is None:
        # Intenta fallback a tabla legacy user_social_accounts
        if _desconectar_legacy(db, current_user.id, platform_norm):
            return {"message": f"Cuenta de {platform_norm} desconectada exitosamente"}
        # Si no existe, igual retorna éxito idempotente
        return {"message": f"Cuenta de {platform_norm} desconectada exitosamente"}

    _eliminar_cuenta_orm(db, account, current_user.id, platform_norm)

    # Limpieza adicional en tabla legacy si existe
    _limpiar_tabla_legacy(db, current_user.id, platform_norm)

    return {"message": f"Cuenta de {platform_norm} desconectada exitosamente"}


@router.get("/youtube/connect", summary="Obtener URL de autorización OAuth2 de YouTube")
def youtube_connect(current_user: CurrentUser):
    auth_url = yt_get_youtube_auth_url(str(current_user.id))
    return {"auth_url": auth_url}


def _redirect_oauth(frontend_base: str, integration: str, status_value: str, extra: str | None = None, con_message: bool = False) -> RedirectResponse:
    """RedirectResponse 302 al dashboard de integraciones con los params del OAuth."""
    params = {"integration": integration, "status": status_value}
    if extra:
        if con_message:
            params["message"] = extra
        params["error"] = extra
    url = f"{frontend_base}/dashboard/integrations?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


def _guardar_tokens_youtube(frontend_base: str, db, code: str, state: str | None) -> RedirectResponse:
    """Exchange + guardado de tokens de YouTube; redirect de error si el state es inválido."""
    tokens = yt_exchange_code_for_tokens(code)

    user_id: str | None = None
    if state:
        user_id = yt_decode_state(state)

    if not user_id:
        return _redirect_oauth(frontend_base, "youtube", "error", "invalid_state")

    yt_save_youtube_tokens(db, user_id, tokens)
    return _redirect_oauth(frontend_base, "youtube", "success")


@router.get("/youtube/callback", summary="Callback OAuth2 de YouTube")
def youtube_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    frontend_base = _get_frontend_base()

    if error:
        return _redirect_oauth(frontend_base, "youtube", "error", error)

    if not code:
        return _redirect_oauth(frontend_base, "youtube", "error", "missing_code")

    try:
        return _guardar_tokens_youtube(frontend_base, db, code, state)
    except Exception as exc:
        return _redirect_oauth(frontend_base, "youtube", "error", str(exc)[:200])


def _client_id_instagram() -> str:
    """Client id de Instagram/Meta desde el entorno (vacío si no hay)."""
    import os as _os

    return (_os.getenv("INSTAGRAM_CLIENT_ID") or _os.getenv("META_APP_ID") or _os.getenv("FB_CLIENT_ID") or "").strip()


def _exigir_client_id_instagram() -> None:
    """HTTPException 500 si el servicio de Instagram no está disponible o falta el client id."""
    from fastapi import HTTPException

    if ig_get_instagram_auth_url is None:
        raise HTTPException(status_code=500, detail="Instagram service no disponible")
    if not _client_id_instagram():
        raise HTTPException(status_code=500, detail="INSTAGRAM_CLIENT_ID / META_APP_ID no está configurado en el archivo .env del backend")


@router.get("/instagram/connect", summary="Obtener URL de autorización OAuth2 de Instagram (Meta)")
def instagram_connect(current_user: CurrentUser):
    _exigir_client_id_instagram()
    logger.info("[OAUTH CONNECT] Generando URL para user_id: %s", current_user.id)
    auth_url = ig_get_instagram_auth_url(str(current_user.id))
    logger.info("[OAUTH CONNECT] URL generada: %s", auth_url)
    return {"auth_url": auth_url, "url": auth_url}


def _user_id_de_state_ig(state: str) -> str | None:
    """user_id decodificado del state de Instagram (fallback al decoder de YouTube)."""
    try:
        return ig_decode_state(state)  # type: ignore
    except Exception:
        return yt_decode_state(state)


def _guardar_tokens_instagram(db, code: str, state: str | None) -> None:
    """Exchange + guardado de tokens de Instagram; ValueError si el state es inválido."""
    assert ig_exchange_code_for_tokens is not None
    tokens = ig_exchange_code_for_tokens(code)

    user_id: str | None = None
    if state:
        user_id = _user_id_de_state_ig(state)

    if not user_id:
        raise ValueError("invalid_state")

    assert ig_save_instagram_tokens is not None
    ig_save_instagram_tokens(db, user_id, tokens)


@router.get("/instagram/callback", summary="Callback OAuth2 de Instagram (Meta)")
def instagram_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    frontend_base = _get_frontend_base()

    if error:
        return _redirect_oauth(frontend_base, "instagram", "error", error, con_message=True)

    if not code:
        return _redirect_oauth(frontend_base, "instagram", "error", "missing_code", con_message=True)

    try:
        _guardar_tokens_instagram(db, code, state)
        return _redirect_oauth(frontend_base, "instagram", "success", con_message=True)
    except Exception as e:
        logger.error("Error en callback de Instagram: %s", str(e), exc_info=True)
        return _redirect_oauth(frontend_base, "instagram", "error", "Error al guardar token", con_message=True)


def _tiktok_service_ok() -> None:
    """HTTPException 503 con mensaje claro si el servicio o las credenciales faltan."""
    from fastapi import HTTPException as _HTTPException

    if tt_get_tiktok_auth_url is None or tt_generate_pkce_pair is None:
        raise _HTTPException(status_code=503, detail="TikTok service no disponible en el backend")
    if not _tiktok_configurado():
        raise _HTTPException(
            status_code=503,
            detail="TikTok no está configurado en el servidor: define TIKTOK_CLIENT_KEY y TIKTOK_CLIENT_SECRET en el archivo .env del backend",
        )


def _tiktok_configurado() -> bool:
    """True si TIKTOK_CLIENT_KEY/SECRET tienen valor (leído fresco del entorno)."""
    import os as _os

    return bool((_os.getenv("TIKTOK_CLIENT_KEY") or "").strip()) and bool((_os.getenv("TIKTOK_CLIENT_SECRET") or "").strip())


@router.get("/tiktok/connect", summary="Obtener URL de autorización OAuth2 de TikTok")
def tiktok_connect(current_user: CurrentUser):
    from fastapi import HTTPException as _HTTPException

    _tiktok_service_ok()
    logger.info("[OAUTH CONNECT] Generando URL TikTok para user_id: %s", current_user.id)
    verifier, challenge = tt_generate_pkce_pair()
    # El state DEBE persistir user_id + code_verifier (el callback los usa para el
    # exchange PKCE); social_common.encode_state solo guarda user_id, por eso se
    # construye inline con base64url y se decodifica en _user_id_y_verifier_de_state.
    state_data = {"user_id": str(current_user.id), "code_verifier": verifier}
    encoded_state = _encode_state_con_verifier(state_data)
    try:
        auth_url = tt_get_tiktok_auth_url(state=encoded_state, code_challenge=challenge)
    except ValueError as ve:
        # Config faltante detectada en el service → mensaje claro (no 500 genérico)
        raise _HTTPException(status_code=503, detail=str(ve).replace("[TIKTOK ERROR] ", "")) from ve
    logger.info("[OAUTH CONNECT] TikTok URL generada: %s", auth_url)
    return {"auth_url": auth_url, "url": auth_url}


def _encode_state_con_verifier(state_data: dict) -> str:
    """base64url del JSON {user_id, code_verifier} — reversible por _user_id_y_verifier_de_state."""
    import base64 as _b64
    import json as _json

    return _b64.urlsafe_b64encode(_json.dumps(state_data, separators=(",", ":")).encode()).decode().rstrip("=")


def _decodificar_json_state_tiktok(state: str):
    """Dict decodificado del state base64 de TikTok; None si no se pudo decodificar; {} si no es dict."""
    import base64 as _b64
    import json as _json

    padded = state + "=" * (-len(state) % 4)
    try:
        decoded = _b64.urlsafe_b64decode(padded.encode()).decode()
        data = _json.loads(decoded)
    except Exception:
        return None
    if isinstance(data, dict):
        return data
    return {}


def _valor_de_data(data: dict, key: str) -> str | None:
    """Valor string del campo del state decodificado (None si falta)."""
    return str(data.get(key)) if data.get(key) else None


def _user_id_de_state_fallback(state: str) -> str | None:
    """user_id del state vía decoders legacy (tiktok, luego youtube)."""
    try:
        return tt_decode_state(state)  # type: ignore
    except Exception:
        try:
            return yt_decode_state(state)
        except Exception:
            return None


def _code_verifier_de_state(state: str) -> str | None:
    """code_verifier re-leído del state base64 (segunda pasada)."""
    import base64 as _b64
    import json as _json

    try:
        padded2 = state + "=" * (-len(state) % 4)
        d2 = _json.loads(_b64.urlsafe_b64decode(padded2.encode()).decode())
        if isinstance(d2, dict) and d2.get("code_verifier"):
            return str(d2.get("code_verifier"))
    except Exception:
        pass
    return None


def _user_id_y_verifier_de_state(state: str | None) -> tuple[str | None, str | None]:
    """(user_id, code_verifier) resueltos desde el state de TikTok (con fallback legacy)."""
    if not state:
        return None, None
    data = _decodificar_json_state_tiktok(state)
    if data is None:
        return _user_id_de_state_fallback(state), None
    user_id = _valor_de_data(data, "user_id")
    code_verifier = _valor_de_data(data, "code_verifier")
    if not code_verifier:
        code_verifier = _code_verifier_de_state(state)
    return user_id, code_verifier


def _guardar_tokens_tiktok(db, code: str, state: str | None) -> None:
    """Resuelve el state, hace el exchange y guarda los tokens; ValueError si falta algo."""
    assert tt_exchange_tiktok_code is not None
    user_id, code_verifier = _user_id_y_verifier_de_state(state)
    if not user_id:
        raise ValueError("invalid_state")
    if not code_verifier:
        raise ValueError("missing_code_verifier")
    tokens = tt_exchange_tiktok_code(code=code, code_verifier=code_verifier)
    assert tt_save_tiktok_tokens is not None
    tt_save_tiktok_tokens(db, user_id, tokens)


@router.get("/tiktok/callback", summary="Callback OAuth2 de TikTok")
def tiktok_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    frontend_base = _get_frontend_base()

    if error:
        return _redirect_oauth(frontend_base, "tiktok", "error", error, con_message=True)

    if not code:
        return _redirect_oauth(frontend_base, "tiktok", "error", "missing_code", con_message=True)

    try:
        _guardar_tokens_tiktok(db, code, state)
        return _redirect_oauth(frontend_base, "tiktok", "success", con_message=True)
    except Exception as e:
        logger.error("Error en callback de TikTok: %s", str(e), exc_info=True)
        return _redirect_oauth(frontend_base, "tiktok", "error", "Error al guardar token", con_message=True)
