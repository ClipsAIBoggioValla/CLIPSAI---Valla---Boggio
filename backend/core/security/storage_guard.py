from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from urllib.parse import quote, urlencode


def _signing_key() -> bytes:
    return os.getenv("STORAGE_SIGN_KEY", "clipsai-dev-sign-key").encode()


def generate_presigned_url(
    object_key: str,
    expires_in: int = 3600,
    base_url: str | None = None,
) -> str:
    base = base_url or os.getenv("STORAGE_BASE_URL", "https://storage.clipsai.local")
    expires_at = int(time.time()) + int(expires_in)
    to_sign = f"{object_key}:{expires_at}".encode()
    sig = hmac.new(_signing_key(), to_sign, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    qs = urlencode({"expires": expires_at, "sig": sig_b64})
    key = quote(object_key.lstrip("/"))
    return f"{base.rstrip('/')}/{key}?{qs}"


def verify_presigned_url(url: str, object_key: str) -> bool:
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    try:
        expires = int(qs.get("expires", ["0"])[0])
        sig = qs.get("sig", [""])[0]
    except Exception:
        return False
    if time.time() > expires:
        return False
    expected = generate_presigned_url(object_key, expires_in=expires - int(time.time()), base_url=f"{parsed.scheme}://{parsed.netloc}")
    exp_sig = parse_qs(urlparse(expected).query).get("sig", [""])[0]
    return hmac.compare_digest(sig, exp_sig)
