"""Entrypoint de la aplicacion FastAPI (Backend #1)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import auth, clips, jobs, stats, users, videos

from .models import Clip, Job, Usuario, Video  # noqa: F401 — registra modelos para create_all

_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS transcription_filepath VARCHAR;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS transcript TEXT;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION;"))
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result_metadata JSONB;"))
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_message TEXT;"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS video_id UUID;"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION;"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS tags JSONB;"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ready';"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;"))
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);"))
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS theme_preference VARCHAR(20) DEFAULT 'dark';"))
        try:
            conn.execute(text("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS chk_jobs_status;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS chk_jobs_stats;"))
        except Exception:
            pass
        conn.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_jobs_status') THEN "
                "ALTER TABLE jobs ADD CONSTRAINT chk_jobs_status "
                "CHECK (lower(status) IN ('pending','processing','completed','failed')); "
                "END IF; END $$;"
            )
        )
        conn.commit()
    yield


app = FastAPI(
    title=_settings.app_name,
    version="0.1.0",
    description=(
        "Backend FastAPI de clipsai — autenticacion (Issue 3) + videos/jobs (Issue 4). "
        "Se conecta a la Postgres dockerizada de la Issue 1."
    ),
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def handle_options_preflight(request, call_next):  # type: ignore[no-untyped-def]
    if request.method == "OPTIONS":
        from fastapi.responses import Response

        response = Response(status_code=200)
        origin = request.headers.get("origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, PUT, DELETE, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    return await call_next(request)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(videos.router)
app.include_router(jobs.router)
app.include_router(clips.router)
app.include_router(stats.router)


@app.get("/health", tags=["infra"], summary="Healthcheck simple")
def health() -> dict[str, str]:
    return {"status": "ok"}
