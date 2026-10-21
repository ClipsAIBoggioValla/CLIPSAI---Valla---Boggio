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
