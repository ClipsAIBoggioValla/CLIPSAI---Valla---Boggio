"""Wrappers de cifrado/descifrado de tokens OAuth sobre backend.core.security.vault."""
from __future__ import annotations

from typing import Any

from backend.core.security.vault import decrypt_token, encrypt_token


def cifrar_token(valor: Any) -> Any:
    """Token cifrado con AESGCM; devuelve el valor tal cual si es None/vacío o falla."""
    if not valor:
        return valor
    return encrypt_token(str(valor))


def descifrar_token(valor: Any) -> Any:
    """Token en claro; si no es descifrable (legacy en texto plano) devuelve el valor tal cual."""
    if not valor:
        return valor
    try:
        return decrypt_token(str(valor))
    except Exception:
        return valor
