"""Configuracion de la aplicacion.

Utiliza python-dotenv para cargar .env desde la raiz del proyecto.
En Docker Compose las variables ya vienen definidas por el servicio,
así que pydantic-settings las leyera del ambiente directamente.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

# Cargar .env desde la raiz del proyecto (un nivel arriba de /app/)
# Esto asegura que tanto en desarrollo local como en Docker se encuentre el archivo.
_env_loaded = load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    override=False,
)

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
    database_url: str = Field(
        default="postgresql+psycopg2://clipsai:changeme@db:5432/clipsai",
        validation_alias="DATABASE_URL",
    )

    # ---- JWT ----
    jwt_secret: str = Field(..., validation_alias="JWT_SECRET", min_length=16)
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