"""Seed the DB with realistic sample data so the UI is usable out of the box."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.db.models import (
    Area,
    Furnished,
    GeometryType,
    Listing,
    Notification,
    ScrapeRun,
    ScrapeRunStatus,
    SearchProfile,
    Source,
)
from home_seek.db.session import get_database
from home_seek.pipeline.dedup import compute_fingerprint


async def seed_all(*, reset: bool = False) -> None:
    """Insert a curated set of areas, profiles, listings, runs, notifications.

    Idempotent by default: existing rows are kept. Pass ``reset=True`` to wipe
    and recreate everything (useful in dev when models change).
    """
    db = get_database()
    if reset:
        await db.drop_all()
    await db.create_all()
    async with db.session() as session:
        await _seed_areas(session)
        await session.flush()
        await _seed_profiles(session)
        await session.flush()
        await _seed_listings_runs_notifications(session)


# ---------------------------------------------------------------------------
# Areas (3 examples covering both geometry types)
# ---------------------------------------------------------------------------

_AREAS: list[dict[str, object]] = [
    {
        "name": "פלורנטין",
        "city": "תל אביב",
        "geometry_type": GeometryType.RADIUS,
        "center_lat": 32.0566,
        "center_lng": 34.7657,
        "radius_meters": 800,
        "yad2_city_id": 5000,
        "yad2_neighborhood_ids": [1483],
    },
    {
        "name": "רמת אביב צפון",
        "city": "תל אביב",
        "geometry_type": GeometryType.RADIUS,
        "center_lat": 32.1130,
        "center_lng": 34.7986,
        "radius_meters": 1200,
        "yad2_city_id": 5000,
        "yad2_neighborhood_ids": [1530],
    },
    {
        "name": "מרכז רמת גן (משולש)",
        "city": "רמת גן",
        "geometry_type": GeometryType.POLYGON,
        "polygon_json": {
            "type": "Polygon",
            "coordinates": [
                [
                    [34.8120, 32.0800],
                    [34.8260, 32.0800],
                    [34.8190, 32.0890],
                    [34.8120, 32.0800],
                ]
            ],
        },
    },
]


async def _seed_areas(session: AsyncSession) -> None:
    for spec in _AREAS:
        existing = await session.scalar(select(Area).where(Area.name == spec["name"]))
        if existing is None:
            session.add(Area(**spec))


# ---------------------------------------------------------------------------
# Search profiles - one per area
# ---------------------------------------------------------------------------


async def _seed_profiles(session: AsyncSession) -> None:
    profiles_spec = [
        {
            "area_name": "פלורנטין",
            "name": "זוג צעיר - עד 8K",
            "min_price": 5000,
            "max_price": 8500,
            "min_rooms": 2.0,
            "max_rooms": 3.0,
            "requires_balcony": True,
            "furnished": Furnished.ANY,
            "keywords_exclude": ["ללא חלונות", "שותפים"],
        },
        {
            "area_name": "רמת אביב צפון",
            "name": "משפחה - 3-4 חדרים",
            "min_price": 7000,
            "max_price": 12000,
            "min_rooms": 3.0,
            "max_rooms": 4.5,
            "requires_parking": True,
            "requires_elevator": True,
            "furnished": Furnished.ANY,
        },
        {
            "area_name": "מרכז רמת גן (משולש)",
            "name": "סטודיו עד 6.5K",
            "min_price": 0,
            "max_price": 6500,
            "min_rooms": 1.0,
            "max_rooms": 2.5,
            "furnished": Furnished.ANY,
        },
    ]
    for spec in profiles_spec:
        area_name = spec.pop("area_name")
        area = await session.scalar(select(Area).where(Area.name == area_name))
        if area is None:
            continue
        existing = await session.scalar(
            select(SearchProfile).where(
                SearchProfile.area_id == area.id,
                SearchProfile.name == spec["name"],
            )
        )
        if existing is None:
            session.add(SearchProfile(area_id=area.id, **spec))


# ---------------------------------------------------------------------------
# Listings, scrape runs, and notifications (used as historical context).
# ---------------------------------------------------------------------------


_LISTING_SEEDS: list[dict[str, object]] = [
    {
        "source": Source.YAD2,
        "source_id": "yad2-demo-1001",
        "title": "דירת 2 חדרים משופצת בפלורנטין",
        "price": 7600,
        "rooms": 2.0,
        "sqm": 48,
        "floor": 2,
        "total_floors": 4,
        "address": "וושינגטון 14",
        "city": "תל אביב",
        "neighborhood": "פלורנטין",
        "lat": 32.0568,
        "lng": 34.7660,
        "parking": False,
        "elevator": False,
        "balcony": True,
        "description": "דירה משופצת מהיסוד, מרפסת שמש, קרובה למסעדות וקפה",
        "url": "https://example.com/yad2/1001",
    },
    {
        "source": Source.YAD2,
        "source_id": "yad2-demo-1002",
        "title": "סטודיו מהמם בלב פלורנטין",
        "price": 5400,
        "rooms": 1.0,
        "sqm": 28,
        "floor": 1,
        "total_floors": 3,
        "address": "פלורנטין 32",
        "city": "תל אביב",
        "neighborhood": "פלורנטין",
        "lat": 32.0560,
        "lng": 34.7650,
        "parking": False,
        "elevator": False,
        "balcony": False,
        "description": "סטודיו מואר, מטבח חדש, פינוי מיידי",
        "url": "https://example.com/yad2/1002",
    },
    {
        "source": Source.MADLAN,
        "source_id": "madlan-demo-2001",
        "title": "דירת 4 חדרים ברמת אביב",
        "price": 11500,
        "rooms": 4.0,
        "sqm": 105,
        "floor": 5,
        "total_floors": 8,
        "address": "ברודצקי 28",
        "city": "תל אביב",
        "neighborhood": "רמת אביב צפון",
        "lat": 32.1125,
        "lng": 34.7990,
        "parking": True,
        "elevator": True,
        "balcony": True,
        "description": 'דירה מרווחת, חניה כפולה, מעלית, ממ"ד',
        "url": "https://example.com/madlan/2001",
    },
    {
        "source": Source.HOMELESS,
        "source_id": "homeless-demo-3001",
        "title": "דירת 3 חדרים ברמת גן",
        "price": 6400,
        "rooms": 3.0,
        "sqm": 70,
        "floor": 3,
        "total_floors": 4,
        "address": "ביאליק 12",
        "city": "רמת גן",
        "neighborhood": "מרכז העיר",
        "lat": 32.0830,
        "lng": 34.8175,
        "parking": False,
        "elevator": True,
        "balcony": True,
        "description": "דירה מרווחת, קרובה לבורסה",
        "url": "https://example.com/homeless/3001",
    },
    {
        "source": Source.STUB,
        "source_id": "stub-seed-9001",
        "title": "דוגמת stub: דירת 2.5 חדרים",
        "price": 7100,
        "rooms": 2.5,
        "sqm": 55,
        "floor": 3,
        "total_floors": 4,
        "address": "אבן גבירול 78",
        "city": "תל אביב",
        "neighborhood": "פלורנטין",
        "lat": 32.0571,
        "lng": 34.7669,
        "parking": True,
        "elevator": True,
        "balcony": True,
        "description": "דירה שקטה, אופי שמור, מואר",
        "url": "https://example.com/stub/9001",
    },
]


async def _seed_listings_runs_notifications(session: AsyncSession) -> None:
    if (await session.scalar(select(Listing).limit(1))) is not None:
        return  # already seeded

    now = datetime.now(UTC)

    listings: dict[str, Listing] = {}
    for i, spec in enumerate(_LISTING_SEEDS):
        source_value = cast(Source, spec["source"])
        source_id_value = cast(str, spec["source_id"])
        fingerprint = compute_fingerprint(
            source=source_value,
            source_id=source_id_value,
            address=cast("str | None", spec.get("address")),
            price=cast("int | None", spec.get("price")),
            rooms=cast("float | None", spec.get("rooms")),
        )
        listing = Listing(
            fingerprint=fingerprint,
            **spec,
            first_seen_at=now - timedelta(hours=i * 3 + 1),
            last_seen_at=now - timedelta(hours=i * 3 + 1),
            posted_at=now - timedelta(hours=i * 3 + 2),
        )
        session.add(listing)
        listings[source_id_value] = listing

    await session.flush()

    # Scrape runs - one success per source per area + one historical error.
    sources_seen = {Source.YAD2, Source.MADLAN, Source.HOMELESS, Source.STUB}
    areas = list((await session.scalars(select(Area))).all())

    for s_idx, src in enumerate(sources_seen):
        for a_idx, area in enumerate(areas):
            session.add(
                ScrapeRun(
                    source=src,
                    area_id=area.id,
                    started_at=now - timedelta(minutes=15 + s_idx * 3 + a_idx),
                    finished_at=now - timedelta(minutes=14 + s_idx * 3 + a_idx),
                    status=ScrapeRunStatus.SUCCESS,
                    listings_found=8,
                    listings_new=2 if (s_idx + a_idx) % 2 == 0 else 0,
                    notifications_sent=1 if (s_idx + a_idx) % 3 == 0 else 0,
                )
            )

    session.add(
        ScrapeRun(
            source=Source.YAD2,
            area_id=areas[0].id if areas else None,
            started_at=now - timedelta(hours=4),
            finished_at=now - timedelta(hours=4, seconds=-3),
            status=ScrapeRunStatus.BLOCKED,
            listings_found=0,
            listings_new=0,
            error_message="HTTP 403 - cloudflare challenge",
        )
    )

    # Notifications - tie a couple of seed listings to their matching profiles.
    profiles = {
        (p.area_id, p.name): p for p in (await session.scalars(select(SearchProfile))).all()
    }
    areas_by_name = {a.name: a for a in areas}

    notif_specs = [
        ("yad2-demo-1001", "פלורנטין", "זוג צעיר - עד 8K"),
        ("yad2-demo-1002", "פלורנטין", "זוג צעיר - עד 8K"),
        ("madlan-demo-2001", "רמת אביב צפון", "משפחה - 3-4 חדרים"),
        ("homeless-demo-3001", "מרכז רמת גן (משולש)", "סטודיו עד 6.5K"),
    ]
    for sid, area_name, profile_name in notif_specs:
        area_obj = areas_by_name.get(area_name)
        listing_obj = listings.get(sid)
        if area_obj is None or listing_obj is None:
            continue
        profile_obj = profiles.get((area_obj.id, profile_name))
        if profile_obj is None:
            continue
        session.add(
            Notification(
                listing_id=listing_obj.id,
                area_id=area_obj.id,
                profile_id=profile_obj.id,
                sent_at=now - timedelta(hours=2),
                telegram_message_id=None,
            )
        )
