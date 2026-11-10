"""Helpers reutilizables para los tests del backend FastAPI sin PostgreSQL real.

Es un módulo plano (sin pytest) importado por `conftest.py` y por los archivos de
test, para que todos compartan la misma instancia de las clases fakes.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

# Raíz del repo para que `backend_fastapi.app...` se importe sin importar cómo
# se lancen los tests (`python -m pytest`, `pytest`, IDE, etc.).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")


def now_utc() -> datetime:
    return datetime.now(UTC)


# --- fakes de SQLAlchemy ------------------------------------------------------

class FakeResult:
    """Resultado falsificado de `Session.execute()` con el protocolo con los routers usan."""

    def __init__(self, rows: list[Any] | None = None, scalar: Any = None, one: Any = None):
        self._rows = list(rows or [])
        self._scalar = scalar
        self._one = one

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalar(self) -> Any:
        return self._scalar

    def one(self) -> Any:
        if self._one is None and not self._rows:
            raise RuntimeError("FakeResult.one() sin fila configurada")
        return self._one if self._one is not None else self._rows[0]

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalars(self) -> "FakeResult":
        # `db.execute(select(X)).scalars().all() / .first()`
        return self

    def mappings(self) -> "FakeResult":
        # `db.execute(text(...)).mappings().first()` (SQL legacy en social_auth)
        return self


class FakeQuery:
    """`query(Model).filter(...)` — devuelve filas preseleccionadas."""

    def __init__(self, rows: list[Any] | None = None):
        self.rows = list(rows or [])

    def filter(self, *args: Any, **kwargs: Any) -> "FakeQuery":  # noqa: ARG002
        return self

    def all(self) -> list[Any]:
        return list(self.rows)

    def first(self) -> Any:
        return self.rows[0] if self.rows else None


class FakeSession:
    """Sesión falsa suficiente para los routers del backend.

    Configuración por test:
    - `session.seed(obj, ...)` alimenta `db.get(Model, id)` (clases con el __name__ del modelo).
    - `session.push_result(FakeResult(...))` FIFO para `db.execute(...)`.
    - `session.scalar_value` para `db.scalar(...)`.
    - `session.query_rows` para `db.query(Model).filter(...).all()/first()`.
    - `db.refresh(obj)` rellena id/created_at si faltan (simula el flush).
    - `session.commit_error` inyecta un error de integridad en `db.commit()`.
    """

    def __init__(self) -> None:
        self.store: dict[tuple[str, Any], Any] = {}
        self.results: list[FakeResult] = []
        self.default_result = FakeResult()
        self.scalar_value: Any = None
        self.scalar_results: list[Any] = []
        self.query_rows: list[Any] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.commits = 0
        self.commit_error: Exception | None = None

    def seed(self, *objs: Any) -> None:
        for obj in objs:
            if obj.id is not None:
                self.store[(type(obj).__name__, obj.id)] = obj

    def push_result(self, result: FakeResult) -> None:
        self.results.append(result)

    def get(self, model: Any, pk: Any) -> Any:
        return self.store.get((model.__name__, pk))

    def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:  # noqa: ARG002
        return self.results.pop(0) if self.results else self.default_result

    def scalar(self, stmt: Any) -> Any:  # noqa: ARG002
        return self.scalar_results.pop(0) if self.scalar_results else self.scalar_value

    def query(self, model: Any) -> FakeQuery:
        return FakeQuery(self.query_rows)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass

    def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    def refresh(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now_utc()
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now_utc()


# --- modelos de prueba (nombre de clase = tabla que `db.get` busca) -----------

def _named_namespace(name: str) -> type[Any]:
    cls = type(name, (SimpleNamespace,), {})
    cls.__name__ = name
    return cls


UsuarioModel = _named_namespace("Usuario")
VideoModel = _named_namespace("Video")
JobModel = _named_namespace("Job")
ClipModel = _named_namespace("Clip")
SocialAccountModel = _named_namespace("SocialAccount")


# --- factories ----------------------------------------------------------------

def make_usuario(**overrides: Any) -> Any:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="$2b$12$hashpropsrestadoprueba12345678901234567890",
        full_name="Usuaria de Prueba",
        avatar_url=None,
        theme_preference="dark",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    defaults.update(overrides)
    return UsuarioModel(**defaults)


def make_video(user_id: Any, **overrides: Any) -> Any:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=user_id,
        original_filename="video.mp4",
        filename="video.mp4",  # la API de listar expone `filename`
        file_path="/storage/uploads/video.mp4",
        transcription_filepath="/storage/uploads/video.txt",
        transcript="00:00:00 - Hola mundo\n00:00:05 - Continua",
        duration_seconds=120.0,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    defaults.update(overrides)
    return VideoModel(**defaults)


def make_job(video_id: Any, **overrides: Any) -> Any:
    defaults = dict(
        id=uuid.uuid4(),
        video_id=video_id,
        status="completed",
        progress=100,
        error_message=None,
        result_metadata={},
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    defaults.update(overrides)
    return JobModel(**defaults)


def make_clip(job_id: Any, video_id: Any | None = None, **overrides: Any) -> Any:
    defaults = dict(
        id=uuid.uuid4(),
        job_id=job_id,
        video_id=video_id,
        title="Clip de prueba",
        start_time=10.0,
        end_time=45.0,
        score=72.0,
        tags={"has_ass": True, "has_hook": True},
        storage_path="/storage/clips/clip.mp4",
        status="ready",
        publication_status="draft",
        social_network=None,
        published_platform=None,
        social_post_id=None,
        social_post_url=None,
        published_at=None,
        error_log=None,
        transcript=None,  # export usa getattr(clip, "transcript")
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    defaults.update(overrides)
    return ClipModel(**defaults)


def make_social_account(user_id: Any, platform: str = "youtube", **overrides: Any) -> Any:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=user_id,
        platform=platform,
        platform_account_id="acct-123",
        platform_username="canalreal",
        access_token="token-social",
        refresh_token="refresh-social",
        token_expires_at=now_utc(),
        account_name="Canal Real",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    defaults.update(overrides)
    return SocialAccountModel(**defaults)


# --- cliente http -------------------------------------------------------------

def build_client(
    db: FakeSession,
    user: Any | None = None,
    use_real_auth: bool = False,
) -> "TestClient":  # noqa: F821
    """TestClient con overrides de dependencias (sin lifespan, sin DB).

    `use_real_auth=True` deja correr el `get_current_user` real (JWT + consulta por
    db.execute con FakeResult); `user` alimenta el override de usuario autenticado.
    """
    from backend_fastapi.app.deps import get_current_user, get_db
    from backend_fastapi.app.main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db
    if use_real_auth:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = lambda: user or make_usuario()
    return TestClient(app)
