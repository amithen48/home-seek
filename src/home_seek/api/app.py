"""FastAPI app factory + lifespan management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from home_seek import __version__
from home_seek.api.routes import areas, dashboard, listings, notifications, pipeline, profiles, runs
from home_seek.config import get_settings
from home_seek.db.session import get_database, init_db
from home_seek.logging_setup import configure_logging, get_logger
from home_seek.scheduler.jobs import build_scheduler

logger = get_logger(__name__)
_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await init_db()
    settings = get_settings()

    scheduler: AsyncIOScheduler | None = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler()
        scheduler.start()
        logger.info("api.scheduler_started", interval=settings.scrape_interval_minutes)
    else:
        logger.info("api.scheduler_disabled")

    app.state.scheduler = scheduler

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await get_database().dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="home-seek",
        version=__version__,
        description="Apartment rental alert system for Israel.",
        lifespan=lifespan,
    )

    app.include_router(dashboard.router)
    app.include_router(areas.router, prefix="/api")
    app.include_router(profiles.router, prefix="/api")
    app.include_router(listings.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(pipeline.router, prefix="/api")

    static_dir = _WEB_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, object]:
        settings = get_settings()
        return {
            "status": "ok",
            "version": __version__,
            "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
            "live_scrapers_enabled": settings.enable_live_scrapers,
        }

    return app


app = create_app()
