"""Helpers compartidos por los servicios OAuth2 de redes sociales.

Centraliza la codificación/decodificación del `state` (parámetro OAuth2 que
transporta el `user_id`) para evitar duplicación entre `youtube_service`,
`instagram_service` y `tiktok_service`.
"""
from __future__ import annotations

import base64
import json


def encode_state(user_id: str) -> str:
    """Codifica el user_id en un state opaco para el flujo OAuth2."""
    payload = json.dumps({"user_id": str(user_id)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_state(state: str) -> str | None:
    """Decodifica el state y devuelve el user_id, o None si no es válido."""
    if not state:
        return None
    padded = state + "=" * (-len(state) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            decoded = decoder(padded.encode()).decode()
            try:
                data = json.loads(decoded)
                if isinstance(data, dict) and "user_id" in data:
                    return str(data["user_id"])
            except Exception:
                pass
            return decoded
        except Exception:
            continue
    return state


def validate_user_id(user_id: str) -> "uuid.UUID":
    """Valida que user_id sea un UUID válido y lo devuelve; lanza ValueError si no."""
    import uuid

    try:
        return uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ValueError(f"user_id inválido: {user_id}") from exc


def require_access_token(tokens: dict) -> str:
    """Extrae access_token de tokens, lanza ValueError si falta."""
    access_token = tokens.get("access_token")
    if not access_token:
        raise ValueError("tokens sin access_token")
    return str(access_token)
