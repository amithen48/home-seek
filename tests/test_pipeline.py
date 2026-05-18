"""End-to-end pipeline test using StubScraper against a real (in-memory) DB."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from home_seek.db.models import Listing, Notification, ScrapeRun
from home_seek.db.seed import seed_all
from home_seek.db.session import Database
from home_seek.pipeline.runner import run_once
from home_seek.scrapers import StubScraper
from home_seek.scrapers.base import ScraperRegistry


@pytest.mark.asyncio
async def test_pipeline_run_once_inserts_listings_and_notifies(database: Database) -> None:
    await seed_all(reset=False)

    registry = ScraperRegistry()
    registry.register(StubScraper(seed=42, listings_per_run=6))

    summary = await run_once(registry=registry, dry_run=True)

    assert summary.areas_processed > 0
    assert summary.listings_found > 0
    # On the very first run all stub listings are brand new.
    assert summary.listings_new > 0

    async with database.session() as session:
        listings_count = await session.scalar(select(Listing).order_by(Listing.id))
        runs = list((await session.scalars(select(ScrapeRun))).all())
        notifs = list((await session.scalars(select(Notification))).all())

    assert listings_count is not None
    assert any(r.listings_new > 0 for r in runs)
    # Some notifications must have been recorded (dry-run still records).
    assert len(notifs) >= 1


@pytest.mark.asyncio
async def test_pipeline_run_twice_is_idempotent(database: Database) -> None:
    await seed_all(reset=False)
    registry = ScraperRegistry()
    registry.register(StubScraper(seed=7, listings_per_run=4))

    first = await run_once(registry=registry, dry_run=True)
    second = await run_once(registry=registry, dry_run=True)

    # Same minute → same seed material → same listings → nothing new.
    assert second.listings_new == 0
    assert first.notifications_sent >= second.notifications_sent
