"""APScheduler wiring for the periodic scrape job."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from home_seek.config import get_settings
from home_seek.logging_setup import get_logger
from home_seek.pipeline.runner import run_once
from home_seek.scrapers import StubScraper, scrapers
from home_seek.scrapers.base import ScraperRegistry

logger = get_logger(__name__)


def _registry() -> ScraperRegistry:
    """Build the scraper registry based on feature flags.

    Real scrapers (yad2 etc.) require outbound network access. When the
    ``enable_live_scrapers`` flag is off (the default) we register only the
    StubScraper so the system stays usable in dev / restricted environments.
    """
    settings = get_settings()
    # Reset between rebuilds so re-registration is idempotent in tests.
    scrapers._by_source.clear()
    scrapers.register(StubScraper())
    if settings.enable_live_scrapers:
        from home_seek.scrapers.yad2 import Yad2Scraper

        scrapers.register(Yad2Scraper())
    return scrapers


async def scrape_job() -> None:
    logger.info("scheduler.tick")
    registry = _registry()
    summary = await run_once(registry=registry)
    logger.info(
        "scheduler.tick_done",
        areas=summary.areas_processed,
        new=summary.listings_new,
        sent=summary.notifications_sent,
    )


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        scrape_job,
        trigger=IntervalTrigger(minutes=settings.scrape_interval_minutes),
        id="scrape_all",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler


def start_scheduler() -> AsyncIOScheduler:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info(
        "scheduler.started",
        interval_minutes=get_settings().scrape_interval_minutes,
    )
    return scheduler
