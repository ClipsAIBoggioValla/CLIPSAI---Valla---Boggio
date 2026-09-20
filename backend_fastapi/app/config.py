"""Configuracion de la aplicacion.

Utiliza python-dotenv para cargar .env desde la raiz del proyecto.
En Docker Compose las variables ya vienen definidas por el servicio,
así que pydantic-settings las leyera del ambiente directamente.
"""

from __future__ import annotations

import os
import socket
from dotenv import load_dotenv

# Cargar .env desde la raiz del proyecto (un nivel arriba de /app/)
# Esto asegura que tanto en desarrollo local como en Docker se encuentre el archivo.
# También intenta cargar .env en backend_fastapi/.env como fallback local.
for _env_path in (
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
):
    load_dotenv(dotenv_path=_env_path, override=False)


def _is_docker() -> bool:
    try:
        import pathlib

        return pathlib.Path("/.dockerenv").exists()
    except Exception:
        return False


def _resolve_db_host(url: str) -> str:
    is_docker = _is_docker()
    has_db = "@db:" in url or "@db/" in url
    has_local = "@127.0.0.1:" in url or "@localhost:" in url
    if is_docker and has_local:
        return url.replace("@127.0.0.1:", "@db:").replace("@localhost:", "@db:").replace("@127.0.0.1/", "@db/")
    if not is_docker and has_db:
        try:
            socket.getaddrinfo("db", 5432)
            return url
        except socket.gaierror:
            return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")
        except Exception:
            return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")
    return url

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App ----
    app_name: str = "clipsai — FastAPI backend"
    app_env: str = Field(default="development", validation_alias="APP_ENV")

    # ---- Database ----
    # Default al nombre de servicio de docker-compose `db` para que funcie
    # aunque DATABASE_URL no venga en el ambiente (usar .env o docker compose).
    # En host Windows sin Docker DNS, se hace fallback a localhost automáticamente.
    database_url: str = Field(
        default="postgresql+psycopg2://clipsai:changeme@db:5432/clipsai",
        validation_alias="DATABASE_URL",
    )

    def model_post_init(self, __context):  # type: ignore[override]
        object.__setattr__(self, "database_url", _resolve_db_host(self.database_url))
        # Forzar que callbacks usen PUBLIC_BACKEND_URL como base si aún contienen URLs temporales antiguas
        base = self.public_backend_url.rstrip("/") if self.public_backend_url else "https://api.clipsai.xyz"
        if "decorator" in self.google_redirect_uri or "guns-camps" in self.google_redirect_uri or "ngrok" in self.google_redirect_uri:
            object.__setattr__(self, "google_redirect_uri", f"{base}/auth/social/youtube/callback")
        if "decorator" in self.tiktok_redirect_uri or "guns-camps" in self.tiktok_redirect_uri or "ngrok" in self.tiktok_redirect_uri:
            object.__setattr__(self, "tiktok_redirect_uri", f"{base}/auth/social/tiktok/callback")
        if "decorator" in self.instagram_redirect_uri or "guns-camps" in self.instagram_redirect_uri or "ngrok" in self.instagram_redirect_uri:
            object.__setattr__(self, "instagram_redirect_uri", f"{base}/auth/social/instagram/callback")

    # ---- JWT ----
    jwt_secret: str = Field(
        default="dev_secret_key_clipsai_2026_super_secure_local",
        validation_alias="JWT_SECRET",
        min_length=16,
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, validation_alias="JWT_EXPIRE_MINUTES")

    # ---- Backend público permanente ----
    public_backend_url: str = Field(
        default="https://api.clipsai.xyz",
        validation_alias="PUBLIC_BACKEND_URL",
    )
    # ---- Google OAuth (YouTube) ----
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        default="https://api.clipsai.xyz/auth/social/youtube/callback",
        validation_alias="GOOGLE_REDIRECT_URI",
    )
    # ---- TikTok OAuth ----
    tiktok_client_key: str = Field(default="", validation_alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str = Field(default="", validation_alias="TIKTOK_CLIENT_SECRET")
    tiktok_redirect_uri: str = Field(
        default="https://api.clipsai.xyz/auth/social/tiktok/callback",
        validation_alias="TIKTOK_REDIRECT_URI",
    )
    # ---- Meta OAuth (Instagram Graph API) ----
    instagram_client_id: str = Field(default="", validation_alias="INSTAGRAM_CLIENT_ID")
    instagram_client_secret: str = Field(default="", validation_alias="INSTAGRAM_CLIENT_SECRET")
    instagram_redirect_uri: str = Field(
        default="https://api.clipsai.xyz/auth/social/instagram/callback",
        validation_alias="INSTAGRAM_REDIRECT_URI",
    )
    # ---- Facebook OAuth (Meta Graph API - alias para Instagram) ----
    facebook_client_id: str = Field(default="", validation_alias="FACEBOOK_CLIENT_ID")
    facebook_client_secret: str = Field(default="", validation_alias="FACEBOOK_CLIENT_SECRET")
    frontend_redirect_url: str = Field(
        default="http://localhost:3000",
        validation_alias="FRONTEND_REDIRECT_URL",
    )
    frontend_url: str = Field(
        default="http://localhost:3000",
        validation_alias="FRONTEND_URL",
    )

    model_config = SettingsConfigDict(
        # No es estricto con env_file en Docker porque las vars vienen por el servicio.
        # En desarrollo local, python-dotenv ya las cargo arriba.
        env_file="",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instancia singleton de Settings (cacheada)."""
    return Settings()  # type: ignore[call-arg]