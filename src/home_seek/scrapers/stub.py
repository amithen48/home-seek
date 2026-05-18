"""Synthetic scraper used during development and tests.

The real Yad2/Madlan/Homeless scrapers cannot run in environments that block
outbound traffic to the relevant hosts (see ``docs/yad2_api_mapping.md``).
``StubScraper`` returns a deterministic-but-varying batch of fake listings so
the rest of the pipeline (dedup, filter, notify, scheduler, web UI) can be
developed and demoed end-to-end without network access.
"""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, timedelta

from home_seek.db.models import Area, SearchProfile, Source
from home_seek.scrapers.base import BaseScraper, RawListing

# Sample streets per city to make synthetic addresses plausible.
_STREETS_BY_CITY: dict[str, list[str]] = {
    "תל אביב": [
        "אלנבי",
        "דיזנגוף",
        "בן יהודה",
        "רוטשילד",
        "הירקון",
        "וושינגטון",
        "אבן גבירול",
        "פלורנטין",
        "הרצל",
        "יפו",
    ],
    "רמת גן": ["ביאליק", "ז'בוטינסקי", "ארלוזורוב", 'הרא"ה'],
    "חיפה": ["הנביאים", "הרצל", "הגפן", "הגליל"],
    "ירושלים": ["יפו", "בן יהודה", "אגריפס", "המלך ג'ורג'"],
}

_AMENITY_KEYWORDS = [
    "משופצת מהיסוד",
    "מרפסת שמש",
    'ממ"ד',
    "קומה גבוהה",
    "נוף פתוח",
    "קרובה לים",
    "שקטה",
    "מואר",
    "מרכזי",
]


class StubScraper(BaseScraper):
    source = Source.STUB

    def __init__(self, seed: int | None = None, listings_per_run: int = 8) -> None:
        self._seed = seed
        self._listings_per_run = listings_per_run

    async def search(self, area: Area, profile: SearchProfile | None = None) -> list[RawListing]:
        # Seed with area + current minute so each minute produces a new batch,
        # but the same minute is reproducible (helpful for tests).
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        seed_material = f"{area.id}|{now.isoformat()}|{self._seed}".encode()
        rng = random.Random(int(hashlib.sha256(seed_material).hexdigest(), 16))

        streets = _STREETS_BY_CITY.get(area.city, ["הראשונים"])
        listings: list[RawListing] = []

        for i in range(self._listings_per_run):
            street = rng.choice(streets)
            number = rng.randint(1, 180)
            price = rng.choice([5500, 6200, 6800, 7400, 7800, 8500, 9200, 10500, 12000])
            rooms = rng.choice([1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5])
            sqm = int(20 + rooms * rng.randint(15, 22))
            floor = rng.randint(0, 8)
            total_floors = max(floor, rng.randint(2, 12))

            lat, lng = _jitter_around(area, rng, in_area_probability=0.85)

            source_id = (
                f"stub-{area.id}-{now.strftime('%Y%m%d%H%M')}-{i:02d}-{rng.randint(0, 9999):04d}"
            )

            listings.append(
                RawListing(
                    source=Source.STUB,
                    source_id=source_id,
                    url=f"https://example.com/stub/{source_id}",
                    title=f"דירת {rooms} חדרים ב{area.name}",
                    price=price,
                    rooms=rooms,
                    sqm=sqm,
                    floor=floor,
                    total_floors=total_floors,
                    address=f"{street} {number}",
                    city=area.city,
                    neighborhood=area.name,
                    lat=lat,
                    lng=lng,
                    parking=rng.random() < 0.55,
                    elevator=rng.random() < 0.6,
                    balcony=rng.random() < 0.7,
                    furnished=rng.random() < 0.4,
                    pets_allowed=rng.random() < 0.3,
                    description=", ".join(rng.sample(_AMENITY_KEYWORDS, k=3)),
                    images=[
                        f"https://picsum.photos/seed/{source_id}-{n}/600/400" for n in range(2)
                    ],
                    contact_name="פרסום לדוגמה",
                    posted_at=now - timedelta(minutes=rng.randint(0, 240)),
                    raw={"synthetic": True, "seed_material": seed_material.decode()},
                )
            )
        return listings


def _jitter_around(
    area: Area, rng: random.Random, in_area_probability: float
) -> tuple[float | None, float | None]:
    """Produce a fake (lat, lng) somewhere near the area's footprint."""
    center_lat, center_lng = _area_center(area)
    if center_lat is None or center_lng is None:
        return None, None

    # ~0.005 deg lat == ~500 m. Tighten if we want most points inside the area.
    radius_deg = 0.004 if rng.random() < in_area_probability else 0.012
    lat = center_lat + rng.uniform(-radius_deg, radius_deg)
    lng = center_lng + rng.uniform(-radius_deg, radius_deg)
    return lat, lng


def _area_center(area: Area) -> tuple[float | None, float | None]:
    if area.center_lat is not None and area.center_lng is not None:
        return area.center_lat, area.center_lng
    poly = area.polygon_json
    if poly:
        # GeoJSON Polygon: poly['coordinates'][0] is the outer ring (list of [lng, lat]).
        try:
            ring = poly["coordinates"][0]  # type: ignore[index]
            coords = [(float(c[1]), float(c[0])) for c in ring]
        except (KeyError, IndexError, TypeError, ValueError):
            return None, None
        if not coords:
            return None, None
        lat = sum(c[0] for c in coords) / len(coords)
        lng = sum(c[1] for c in coords) / len(coords)
        return lat, lng
    return None, None
