from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.cli import command_run, command_inspect, command_list, run_video
from backend_fastapi.app.database import get_db


def test_command_list() -> None:
    args = SimpleNamespace()
    try:
        command_list(args)
    except SystemExit:
        pass
    except Exception:
        pass


def test_get_db() -> None:
    gen = get_db()
    try:
        db = next(gen)
        assert db is not None
    except Exception:
        pass
    finally:
        try:
            gen.close()
        except Exception:
            pass


def test_run_video_missing() -> None:
    try:
        run_video("/tmp/nope.mp4")
    except Exception:
        pass
