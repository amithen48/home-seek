"""End-to-end pipeline: scrape → dedup → filter → persist → notify.

Designed to be called either ad-hoc (CLI) or by the scheduler. One ``run_once``
call processes all active areas using all registered scrapers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.db.models import (
    Area,
    Listing,
    Notification,
    ScrapeRun,
    ScrapeRunStatus,
    SearchProfile,
    Source,
)
from home_seek.db.session import get_database
from home_seek.logging_setup import get_logger
from home_seek.notify.formatter import format_listing_message
from home_seek.notify.telegram import TelegramNotifier
from home_seek.pipeline.dedup import compute_fingerprint
from home_seek.pipeline.filter import matches_profile
from home_seek.scrapers.base import BaseScraper, RawListing, ScraperRegistry

logger = get_logger(__name__)


@dataclass(slots=True)
class RunSummary:
    started_at: datetime
    finished_at: datetime | None = None
    sources: list[Source] = field(default_factory=list)
    areas_processed: int = 0
    listings_found: int = 0
    listings_new: int = 0
    notifications_sent: int = 0
    errors: list[str] = field(default_factory=list)


async def run_once(
    *,
    registry: ScraperRegistry,
    notifier: TelegramNotifier | None = None,
    dry_run: bool = False,
    sources: list[Source] | None = None,
    area_id: int | None = None,
) -> RunSummary:
    """Process every active area with every registered scraper, once."""
    notifier = notifier or TelegramNotifier()
    summary = RunSummary(
        started_at=datetime.now(UTC),
        sources=[s.source for s in registry.all()],
    )

    db = get_database()
    async with db.session() as session:
        areas = await _load_active_areas(session, area_id=area_id)
        summary.areas_processed = len(areas)

        for scraper in registry.all():
            if sources is not None and scraper.source not in sources:
                continue
            for area in areas:
                await _process_area_with_scraper(
                    scraper=scraper,
                    area=area,
                    session=session,
                    notifier=notifier,
                    summary=summary,
                    dry_run=dry_run,
                )

    summary.finished_at = datetime.now(UTC)
    logger.info(
        "pipeline.run_done",
        areas=summary.areas_processed,
        found=summary.listings_found,
        new=summary.listings_new,
        sent=summary.notifications_sent,
        errors=len(summary.errors),
    )
    return summary


async def _load_active_areas(session: AsyncSession, *, area_id: int | None) -> list[Area]:
    stmt = select(Area).where(Area.active.is_(True))
    if area_id is not None:
        stmt = stmt.where(Area.id == area_id)
    return list((await session.scalars(stmt)).all())


async def _process_area_with_scraper(
    *,
    scraper: BaseScraper,
    area: Area,
    session: AsyncSession,
    notifier: TelegramNotifier,
    summary: RunSummary,
    dry_run: bool,
) -> None:
    run = ScrapeRun(source=scraper.source, area_id=area.id, status=ScrapeRunStatus.RUNNING)
    session.add(run)
    await session.flush()

    profiles = list(area.profiles) if area.profiles else []
    primary_profile = next((p for p in profiles if p.active), None)

    try:
        raw_listings = await scraper.search(area, primary_profile)
    except Exception as exc:
        run.status = ScrapeRunStatus.ERROR
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.now(UTC)
        summary.errors.append(f"{scraper.source.value}/{area.name}: {exc}")
        logger.warning(
            "pipeline.scraper_error",
            source=scraper.source.value,
            area=area.name,
            error=str(exc),
        )
        return

    run.listings_found = len(raw_listings)
    summary.listings_found += len(raw_listings)

    for raw in raw_listings:
        new_listing, listing = await _upsert_listing(session, raw)
        if new_listing:
            run.listings_new += 1
            summary.listings_new += 1

        for profile in profiles:
            if not profile.active:
                continue
            verdict = matches_profile(listing, area, profile)
            if not verdict.matches:
                continue
            sent = await _maybe_notify(
                session=session,
                listing=listing,
                area=area,
                profile=profile,
                notifier=notifier,
                dry_run=dry_run,
            )
            if sent:
                run.notifications_sent += 1
                summary.notifications_sent += 1

    run.status = ScrapeRunStatus.SUCCESS
    run.finished_at = datetime.now(UTC)


async def _upsert_listing(session: AsyncSession, raw: RawListing) -> tuple[bool, Listing]:
    """Insert if new, otherwise update ``last_seen_at``. Returns ``(is_new, listing)``."""
    fingerprint = compute_fingerprint(
        source=raw.source,
        source_id=raw.source_id,
        address=raw.address,
        price=raw.price,
        rooms=raw.rooms,
    )
    existing = await session.scalar(select(Listing).where(Listing.fingerprint == fingerprint))
    now = datetime.now(UTC)
    if existing is not None:
        existing.last_seen_at = now
        existing.is_active = True
        return False, existing

    listing = Listing(
        fingerprint=fingerprint,
        source=raw.source,
        source_id=raw.source_id,
        url=raw.url,
        title=raw.title,
        price=raw.price,
        rooms=raw.rooms,
        sqm=raw.sqm,
        floor=raw.floor,
        total_floors=raw.total_floors,
        address=raw.address,
        city=raw.city,
        neighborhood=raw.neighborhood,
        lat=raw.lat,
        lng=raw.lng,
        parking=raw.parking,
        elevator=raw.elevator,
        balcony=raw.balcony,
        furnished=raw.furnished,
        pets_allowed=raw.pets_allowed,
        description=raw.description,
        images_json=list(raw.images) if raw.images else None,
        contact_name=raw.contact_name,
        contact_phone=raw.contact_phone,
        posted_at=raw.posted_at,
        raw_json=raw.raw,
    )
    session.add(listing)
    await session.flush()
    return True, listing


async def _maybe_notify(
    *,
    session: AsyncSession,
    listing: Listing,
    area: Area,
    profile: SearchProfile,
    notifier: TelegramNotifier,
    dry_run: bool,
) -> bool:
    existing = await session.scalar(
        select(Notification).where(
            Notification.listing_id == listing.id,
            Notification.profile_id == profile.id,
        )
    )
    if existing is not None:
        return False

    text = format_listing_message(listing, area)

    if dry_run:
        logger.info(
            "pipeline.notify.dry_run",
            listing_id=listing.id,
            area=area.name,
            profile=profile.name,
        )
        notif = Notification(
            listing_id=listing.id,
            area_id=area.id,
            profile_id=profile.id,
            telegram_message_id=None,
        )
        session.add(notif)
        await session.flush()
        return True

    result = await notifier.send_message(text)
    notif = Notification(
        listing_id=listing.id,
        area_id=area.id,
        profile_id=profile.id,
        telegram_message_id=result.message_id,
    )
    session.add(notif)
    await session.flush()
    return result.sent
