from __future__ import annotations

import os
import urllib.parse

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from ..deps import CurrentUser, DbSession
from ..services.youtube_service import exchange_code_for_tokens, get_youtube_auth_url, save_youtube_tokens, _decode_state

router = APIRouter(prefix="/auth/social", tags=["Social Auth"])


def _get_frontend_base() -> str:
    base = os.getenv("FRONTEND_REDIRECT_URL", "").strip()
    if not base:
        base = os.getenv("FRONTEND_URL", "").strip()
    if not base:
        base = "http://localhost:3000"
    return base.rstrip("/")


@router.get("/youtube/connect", summary="Obtener URL de autorización OAuth2 de YouTube")
def youtube_connect(current_user: CurrentUser):
    auth_url = get_youtube_auth_url(str(current_user.id))
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
        tokens = exchange_code_for_tokens(code)
    except Exception as exc:
        return redirect_with("error", str(exc)[:200])

    user_id: str | None = None
    if state:
        user_id = _decode_state(state)

    if not user_id:
        return redirect_with("error", "invalid_state")

    try:
        save_youtube_tokens(db, user_id, tokens)
    except Exception as exc:
        return redirect_with("error", str(exc)[:200])

    return redirect_with("success")
