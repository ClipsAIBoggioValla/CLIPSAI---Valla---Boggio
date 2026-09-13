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


@router.get("/status", summary="Estado de integraciones conectadas")
@router.get("/accounts", summary="Estado de integraciones conectadas (alias)", include_in_schema=False)
async def get_social_status(
    current_user: CurrentUser,
    db: DbSession,
):
    import re

    from ..models import SocialAccount

    logger.info("Consulta /status para user_id: %s (tipo: %s)", current_user.id, type(current_user.id))
    accounts = db.query(SocialAccount).filter(SocialAccount.user_id == current_user.id).all()
    logger.info("Cuentas encontradas en BD: %s", [(a.platform, getattr(a, "platform_username", None) or getattr(a, "account_name", None)) for a in accounts])

    status = {
        "instagram": {"connected": False, "username": None, "expires_at": None},
        "youtube": {"connected": False, "username": None, "expires_at": None},
        "tiktok": {"connected": False, "username": None, "expires_at": None},
    }

    fallback_re = re.compile(r"^(instagram|youtube|tiktok)_[0-9a-fA-F]{8}$")

    for acc in accounts:
        logger.info("[STATUS DEBUG] User %s - %s DB Username: %s", current_user.id, acc.platform, acc.platform_username)
        platform = (acc.platform or "").lower()
        if platform in status:
            raw_username = getattr(acc, "platform_username", None) or getattr(acc, "account_name", None)
            if raw_username and fallback_re.match(str(raw_username).strip()):
                raw_username = None
            username_val = raw_username if raw_username and str(raw_username).strip() else None
            if not username_val and platform == "instagram":
                username_val = "Instagram User"
            if not username_val and platform == "tiktok":
                username_val = "TikTok User"
            status[platform] = {
                "connected": True,
                "username": username_val,
                "expires_at": acc.token_expires_at.isoformat() if getattr(acc, "token_expires_at", None) else None,
            }

    return status





def _get_frontend_base() -> str:
    base = os.getenv("FRONTEND_REDIRECT_URL", "").strip()
    if not base:
        base = os.getenv("FRONTEND_URL", "").strip()
    if not base:
        base = "http://localhost:3000"
    return base.rstrip("/")


@router.get("/youtube/connect", summary="Obtener URL de autorización OAuth2 de YouTube")
def youtube_connect(current_user: CurrentUser):
    auth_url = yt_get_youtube_auth_url(str(current_user.id))
    return {"auth_url": auth_url}


@router.get("/youtube/callback", summary="Callback OAuth2 de YouTube")
def youtube_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    frontend_base = _get_frontend_base()

    def redirect_with(status: str, extra: str | None = None) -> RedirectResponse:
        params = {"integration": "youtube", "status": status}
        if extra:
            params["error"] = extra
        url = f"{frontend_base}/dashboard/integrations?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=url, status_code=302)

    if error:
        return redirect_with("error", error)

    if not code:
        return redirect_with("error", "missing_code")

    try:
        tokens = yt_exchange_code_for_tokens(code)
    except Exception as exc:
        return redirect_with("error", str(exc)[:200])

    user_id: str | None = None
    if state:
        user_id = yt_decode_state(state)

    if not user_id:
        return redirect_with("error", "invalid_state")

    try:
        yt_save_youtube_tokens(db, user_id, tokens)
    except Exception as exc:
        return redirect_with("error", str(exc)[:200])

    return redirect_with("success")


@router.get("/instagram/connect", summary="Obtener URL de autorización OAuth2 de Instagram (Meta)")
def instagram_connect(current_user: CurrentUser):
    if ig_get_instagram_auth_url is None:
        from fastapi import HTTPException as _HTTPException

        raise _HTTPException(status_code=500, detail="Instagram service no disponible")
    import os as _os

    _cid = (_os.getenv("INSTAGRAM_CLIENT_ID") or _os.getenv("META_APP_ID") or _os.getenv("FB_CLIENT_ID") or "").strip()
    if not _cid:
        from fastapi import HTTPException as _HTTPException

        raise _HTTPException(status_code=500, detail="INSTAGRAM_CLIENT_ID / META_APP_ID no está configurado en el archivo .env del backend")
    logger.info("[OAUTH CONNECT] Generando URL para user_id: %s", current_user.id)
    auth_url = ig_get_instagram_auth_url(str(current_user.id))
    logger.info("[OAUTH CONNECT] URL generada: %s", auth_url)
    return {"auth_url": auth_url, "url": auth_url}


@router.get("/instagram/callback", summary="Callback OAuth2 de Instagram (Meta)")
def instagram_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    frontend_base = _get_frontend_base()

    def redirect_with(status: str, extra: str | None = None) -> RedirectResponse:
        params = {"integration": "instagram", "status": status}
        if extra:
            params["message"] = extra
            params["error"] = extra
        url = f"{frontend_base}/dashboard/integrations?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=url, status_code=302)

    if error:
        return redirect_with("error", error)

    if not code:
        return redirect_with("error", "missing_code")

    try:
        assert ig_exchange_code_for_tokens is not None
        tokens = ig_exchange_code_for_tokens(code)

        user_id: str | None = None
        if state:
            try:
                user_id = ig_decode_state(state)  # type: ignore
            except Exception:
                user_id = yt_decode_state(state)

        if not user_id:
            raise ValueError("invalid_state")

        assert ig_save_instagram_tokens is not None
        ig_save_instagram_tokens(db, user_id, tokens)
        return redirect_with("success")
    except Exception as e:
        logger.error("Error en callback de Instagram: %s", str(e), exc_info=True)
        return redirect_with("error", "Error al guardar token")


@router.get("/tiktok/connect", summary="Obtener URL de autorización OAuth2 de TikTok")
def tiktok_connect(current_user: CurrentUser):
    if tt_get_tiktok_auth_url is None or tt_generate_pkce_pair is None:
        from fastapi import HTTPException as _HTTPException

        raise _HTTPException(status_code=500, detail="TikTok service no disponible")
    import base64 as _b64
    import json as _json
    import os as _os

    _cid = (_os.getenv("TIKTOK_CLIENT_KEY") or "").strip()
    if not _cid:
        from fastapi import HTTPException as _HTTPException

        raise _HTTPException(status_code=500, detail="TIKTOK_CLIENT_KEY no está configurado en el archivo .env del backend")
    logger.info("[OAUTH CONNECT] Generando URL TikTok para user_id: %s", current_user.id)
    verifier, challenge = tt_generate_pkce_pair()
    state_data = {"user_id": str(current_user.id), "code_verifier": verifier}
    encoded_state = _b64.urlsafe_b64encode(_json.dumps(state_data, separators=(",", ":")).encode()).decode().rstrip("=")
    auth_url = tt_get_tiktok_auth_url(state=encoded_state, code_challenge=challenge)
    logger.info("[OAUTH CONNECT] TikTok URL generada: %s", auth_url)
    return {"auth_url": auth_url, "url": auth_url}


@router.get("/tiktok/callback", summary="Callback OAuth2 de TikTok")
def tiktok_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    frontend_base = _get_frontend_base()

    def redirect_with(status: str, extra: str | None = None) -> RedirectResponse:
        params = {"integration": "tiktok", "status": status}
        if extra:
            params["message"] = extra
            params["error"] = extra
        url = f"{frontend_base}/dashboard/integrations?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=url, status_code=302)

    if error:
        return redirect_with("error", error)

    if not code:
        return redirect_with("error", "missing_code")

    try:
        assert tt_exchange_tiktok_code is not None
        import base64 as _b64
        import json as _json

        user_id: str | None = None
        code_verifier: str | None = None
        if state:
            padded = state + "=" * (-len(state) % 4)
            try:
                decoded = _b64.urlsafe_b64decode(padded.encode()).decode()
                data = _json.loads(decoded)
                if isinstance(data, dict):
                    user_id = str(data.get("user_id")) if data.get("user_id") else None
                    code_verifier = str(data.get("code_verifier")) if data.get("code_verifier") else None
            except Exception:
                try:
                    user_id = tt_decode_state(state)  # type: ignore
                except Exception:
                    try:
                        user_id = yt_decode_state(state)
                    except Exception:
                        user_id = None
            if not code_verifier and state:
                try:
                    padded2 = state + "=" * (-len(state) % 4)
                    d2 = _json.loads(_b64.urlsafe_b64decode(padded2.encode()).decode())
                    if isinstance(d2, dict) and d2.get("code_verifier"):
                        code_verifier = str(d2.get("code_verifier"))
                except Exception:
                    pass

        if not user_id:
            raise ValueError("invalid_state")
        if not code_verifier:
            raise ValueError("missing_code_verifier")

        tokens = tt_exchange_tiktok_code(code=code, code_verifier=code_verifier)

        assert tt_save_tiktok_tokens is not None
        tt_save_tiktok_tokens(db, user_id, tokens)
        return redirect_with("success")
    except Exception as e:
        logger.error("Error en callback de TikTok: %s", str(e), exc_info=True)
        return redirect_with("error", "Error al guardar token")
