from __future__ import annotations

import uuid

from backend_fastapi.app.services import social_common as sc


def test_encode_decode_state_roundtrip():
    uid = str(uuid.uuid4())
    st = sc.encode_state(uid)
    assert sc.decode_state(st) == uid


def test_decode_state_empty():
    assert sc.decode_state("") is None


def test_decode_state_invalid_shape():
    # state that is not valid base64/json -> returns state itself (fallback)
    out = sc.decode_state("!!!not-base64!!!")
    assert isinstance(out, str)
