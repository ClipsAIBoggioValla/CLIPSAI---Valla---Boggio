from __future__ import annotations

import base64
import os
from typing import Tuple

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


def _get_key() -> bytes:
    raw = os.getenv("VAULT_KEY")
    if raw:
        try:
            key = base64.b64decode(raw)
            if len(key) == 32:
                return key
        except Exception:
            pass
        if len(raw.encode()) == 32:
            return raw.encode()
    return b"\x00" * 32 if not _HAS_CRYPTO else AESGCM.generate_key(bit_length=256)


def encrypt_token(plaintext: str, key: bytes | None = None) -> str:
    k = key or _get_key()
    if not _HAS_CRYPTO:
        return base64.b64encode(f"vault:{plaintext}".encode()).decode()
    aesgcm = AESGCM(k)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_token(token: str, key: bytes | None = None) -> str:
    k = key or _get_key()
    if not _HAS_CRYPTO:
        raw = base64.b64decode(token).decode()
        if raw.startswith("vault:"):
            return raw[len("vault:") :]
        return raw
    data = base64.b64decode(token)
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(k)
    pt = aesgcm.decrypt(nonce, ct, None)
    return pt.decode()
