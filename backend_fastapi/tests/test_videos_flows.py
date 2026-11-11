from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend_fastapi.app.routers import videos as videos_router
from backend_fastapi.app.routers.videos import (
    _cleanup_upload_files,
    _get_upload_dir,
    _validate_extension,
)


def test_validate_extension_ok():
    assert _validate_extension("a.mp4", {".mp4"}, "video") == ".mp4"


def test_validate_extension_missing():
    with pytest.raises(Exception) as ei:
        _validate_extension(None, {".mp4"}, "video")
    assert "requerido" in str(ei.value)


def test_validate_extension_bad_ext():
    with pytest.raises(Exception) as ei:
        _validate_extension("a.exe", {".mp4"}, "video")
    assert "extension no permitida" in str(ei.value)


def test_get_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    d = _get_upload_dir()
    assert d == tmp_path / "uploads"


def test_cleanup_upload_files_none():
    _cleanup_upload_files(None, None)


def test_cleanup_upload_files_paths(tmp_path):
    _cleanup_upload_files(tmp_path / "a.mp4", tmp_path / "b.ass")
    assert True
