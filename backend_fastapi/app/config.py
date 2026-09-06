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

    # ---- JWT ----
    jwt_secret: str = Field(
        default="dev_secret_key_clipsai_2026_super_secure_local",
        validation_alias="JWT_SECRET",
        min_length=16,
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, validation_alias="JWT_EXPIRE_MINUTES")

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