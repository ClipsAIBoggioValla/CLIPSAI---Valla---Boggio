"""Entrypoint de la aplicacion FastAPI (Backend #1)."""

from __future__ import annotations

from fastapi import FastAPI

from .config import get_settings
from .routers import auth

_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version="0.1.0",
    description=(
        "Backend FastAPI de clipsai — autenticacion (Issue 3). "
        "Se conecta a la Postgres dockerizada de la Issue 1."
    ),
)

app.include_router(auth.router)


@app.get("/health", tags=["infra"], summary="Healthcheck simple")
def health() -> dict[str, str]:
    return {"status": "ok"}
