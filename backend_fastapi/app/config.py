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


def _redirect_uri_desactualizada(uri: str) -> bool:
    """True si la URL de callback still apunta a un túnel temporal (ngrok)."""
    return "decorator" in uri or "guns-camps" in uri or "ngrok" in uri


def _normalizar_redirect_uri(uri: str, base: str, path: str) -> str:
    """Fuerza que el callback use PUBLIC_BACKEND_URL como base si aún contiene URLs temporales."""
    if _redirect_uri_desactualizada(uri):
        return f"{base}{path}"
    return uri


def _apunta_a_local(url: str) -> bool:
    """True si la URL apunta al host local."""
    return "@127.0.0.1:" in url or "@localhost:" in url


def _apunta_a_db(url: str) -> bool:
    """True si la URL apunta al host 'db' de Docker."""
    return "@db:" in url or "@db/" in url


def _normalizar_esquema_db(url: str) -> str:
    """Normaliza prefijos de proveedores de nube al dialecto explícito SQLAlchemy.

    Neon / Render / Supabase entregan DATABASE_URL como `postgres://` o
    `postgresql://`; el driver del proyecto es psycopg2 (psycopg2-binary), así
    que se reescribe a `postgresql+psycopg2://`. Los query params (p. ej.
    `?sslmode=require` de Neon) se preservan: solo se reemplaza el esquema.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def _validar_jwt_produccion(settings: "Settings") -> None:
    if (
        settings.app_env.strip().lower() == "production"
        and settings.jwt_secret == "dev_secret_key_clipsai_2026_super_secure_local"
    ):
        raise ValueError("JWT_SECRET debe configurarse con un valor seguro en production")


def _validar_jwt_algoritmo(settings: "Settings") -> None:
    """Solo HMAC simétrico: no permitir none ni algoritmos asimétricos sin claves."""
    permitidos = {"HS256", "HS384", "HS512"}
    if settings.jwt_algorithm.strip().upper() not in permitidos:
        raise ValueError(f"JWT_ALGORITHM debe ser uno de {sorted(permitidos)}")


def _validar_webhook_secret_produccion(settings: "Settings") -> None:
    if (
        settings.app_env.strip().lower() == "production"
        and settings.runpod_webhook_secret.strip() == ""
    ):
        raise ValueError("RUNPOD_WEBHOOK_SECRET debe configurarse en production")


def _resolve_db_host(url: str) -> str:
    if _is_docker() and _apunta_a_local(url):
        return url.replace("@127.0.0.1:", "@db:").replace("@localhost:", "@db:").replace("@127.0.0.1/", "@db/")
    if not _is_docker() and _apunta_a_db(url):
        return _db_url_fuera_de_docker(url)
    return url


def _db_url_fuera_de_docker(url: str) -> str:
    """Fuera de Docker: si el host 'db' resuelve DNS se conserva; si no, fallback a localhost."""
    try:
        socket.getaddrinfo("db", 5432)
        return url
    except socket.gaierror:
        return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")
    except Exception:
        return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")

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
    # NOTE: En produccion esto DEBE venir configurada via entorno .env o docker compose.
    # El valor 'changeme' es solo un placeholder para development local.
    database_url: str = Field(
        default="postgresql+psycopg2://clipsai:changeme_placeholder@db:5432/clipsai",
        validation_alias="DATABASE_URL",
    )

    def model_post_init(self, __context):  # type: ignore[override]
        _validar_jwt_produccion(self)
        _validar_jwt_algoritmo(self)
        _validar_webhook_secret_produccion(self)
        object.__setattr__(
            self,
            "database_url",
            _resolve_db_host(_normalizar_esquema_db(self.database_url)),
        )
        # Forzar que callbacks usen PUBLIC_BACKEND_URL como base si aún contienen URLs temporales antiguas
        base = self.public_backend_url.rstrip("/") if self.public_backend_url else "https://api.clipsai.xyz"
        self._normalizar_callbacks(base)

    def _normalizar_callbacks(self, base: str) -> None:
        """Reescribe los callbacks de OAuth que apunten a túneles temporales."""
        object.__setattr__(self, "google_redirect_uri", _normalizar_redirect_uri(self.google_redirect_uri, base, "/auth/social/youtube/callback"))
        object.__setattr__(self, "tiktok_redirect_uri", _normalizar_redirect_uri(self.tiktok_redirect_uri, base, "/auth/social/tiktok/callback"))
        object.__setattr__(self, "instagram_redirect_uri", _normalizar_redirect_uri(self.instagram_redirect_uri, base, "/auth/social/instagram/callback"))

    # ---- JWT ----
    jwt_secret: str = Field(
        default="dev_secret_key_clipsai_2026_super_secure_local",
        validation_alias="JWT_SECRET",
        min_length=16,
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=480, validation_alias="JWT_EXPIRE_MINUTES")
    runpod_webhook_secret: str = Field(default="", validation_alias="RUNPOD_WEBHOOK_SECRET")

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

    # ---- Claude / LLM (Anthropic) — selección semántica de clips y títulos ----
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5-5", validation_alias="ANTHROPIC_MODEL")
    anthropic_version: str = Field(default="2023-06-01", validation_alias="ANTHROPIC_VERSION")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="anthropic/claude-3.5-sonnet", validation_alias="OPENROUTER_MODEL")
    openrouter_endpoint: str = Field(
        default="https://openrouter.ai/api/v1/chat/completions", validation_alias="OPENROUTER_ENDPOINT"
    )
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    llm_model: str = Field(default="deepseek-chat", validation_alias="MODEL")
    llm_endpoint: str = Field(
        default="https://api.deepseek.com/v1/chat/completions", validation_alias="API_ENDPOINT"
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
