"""Entrypoint de la aplicacion FastAPI (Backend #1)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import auth, clips, export, jobs, metrics, publish, stats, subtitles, users, videos

from .models import Clip, Job, SocialAccount, Usuario, Video  # noqa: F401 — registra modelos para create_all

try:
    import sys
    from pathlib import Path as _Path

    _root = _Path(__file__).resolve().parents[2].parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from backend.api.routes.retrim import router as retrim_router  # type: ignore
    from backend.api.routes.stream import router as stream_router  # type: ignore
except Exception:
    retrim_router = None  # type: ignore
    stream_router = None  # type: ignore

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
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS error_log TEXT;"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS published_platform VARCHAR(50);"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS social_post_id VARCHAR(255);"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS social_post_url TEXT;"))
        conn.execute(text("ALTER TABLE clips ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;"))
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
        try:
            conn.execute(text("ALTER TABLE clips DROP CONSTRAINT IF EXISTS chk_clips_publication_status;"))
        except Exception:
            pass
        conn.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_clips_publication_status') THEN "
                "ALTER TABLE clips ADD CONSTRAINT chk_clips_publication_status "
                "CHECK (lower(publication_status) IN ('draft','scheduled','published','failed','not_published','publishing')); "
                "END IF; END $$;"
            )
        )
        try:
            conn.execute(text("ALTER TABLE clips DROP CONSTRAINT IF EXISTS chk_clips_social_network;"))
        except Exception:
            pass
        conn.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_clips_social_network') THEN "
                "ALTER TABLE clips ADD CONSTRAINT chk_clips_social_network "
                "CHECK (social_network IS NULL OR lower(social_network) IN ('tiktok','youtube_shorts','instagram_reels','youtube','instagram')); "
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


@app.middleware("http")
async def handle_options_preflight(request, call_next):  # type: ignore[no-untyped-def]
    if request.method == "OPTIONS":
        from fastapi.responses import Response

        response = Response(status_code=200)
        origin = request.headers.get("origin", "")
        allowed = [
            "https://decorator-excretory-satin.ngrok-free.dev",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
        if origin in allowed or origin.endswith(".ngrok-free.dev"):
            response.headers["Access-Control-Allow-Origin"] = origin
        elif origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            response.headers["Access-Control-Allow-Origin"] = "https://decorator-excretory-satin.ngrok-free.dev"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, ngrok-skip-browser-warning, X-Requested-With, Accept, Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = "*"
        response.headers["Vary"] = "Origin"
        return response
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://decorator-excretory-satin.ngrok-free.dev",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"https://.*\.ngrok-free\.dev",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning", "X-Requested-With", "Accept", "Origin"],
)

app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(jobs.router)
app.include_router(export.router)
app.include_router(metrics.router)
app.include_router(clips.router)
app.include_router(stats.router)
app.include_router(subtitles.router)
app.include_router(publish.router)
app.include_router(users.router)
app.include_router(users.router, prefix="/api")
if 'retrim_router' in globals() and retrim_router is not None:
    app.include_router(retrim_router)
if 'stream_router' in globals() and stream_router is not None:
    app.include_router(stream_router)


@app.get("/health", tags=["infra"], summary="Healthcheck simple")
def health() -> dict[str, str]:
    return {"status": "ok"}
