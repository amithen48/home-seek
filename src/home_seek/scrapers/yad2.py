"""Yad2 scraper - HTTP client + mapping per ``docs/yad2_api_mapping.md``.

⚠️ This client is a *skeleton*. It cannot be verified end-to-end until we
have network access to ``gw.yad2.co.il``. The HTTP call, header set, and
response mapping are based on the public-knowledge baseline documented in
``docs/yad2_api_mapping.md`` and must be reconciled against a real response
captured from a browser session before production use.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx

from home_seek.config import get_settings
from home_seek.db.models import Area, SearchProfile, Source
from home_seek.logging_setup import get_logger
from home_seek.scrapers.base import BaseScraper, RawListing

logger = get_logger(__name__)

_FEED_URL = "https://gw.yad2.co.il/feed-search/lapi/feed/realestate"
_DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": _DEFAULT_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Origin": "https://www.yad2.co.il",
        "Referer": "https://www.yad2.co.il/realestate/rent",
        "mainland-device-id": str(uuid.uuid4()),
    }


def _build_params(area: Area, profile: SearchProfile | None) -> dict[str, str]:
    params: dict[str, str] = {"propertyGroup": "apartments", "forceLdLoad": "true"}

    if area.yad2_top_area_id is not None:
        params["topArea"] = str(area.yad2_top_area_id)
    if area.yad2_area_id is not None:
        params["area"] = str(area.yad2_area_id)
    if area.yad2_city_id is not None:
        params["city"] = str(area.yad2_city_id)
    if area.yad2_neighborhood_ids:
        params["neighborhood"] = ",".join(str(n) for n in area.yad2_neighborhood_ids)

    if profile is not None:
        if profile.min_price is not None or profile.max_price is not None:
            params["price"] = f"{profile.min_price or 0}-{profile.max_price or 99999}"
        if profile.min_rooms is not None or profile.max_rooms is not None:
            params["rooms"] = f"{profile.min_rooms or 0}-{profile.max_rooms or 20}"
        if profile.min_sqm is not None or profile.max_sqm is not None:
            params["squaremeter"] = f"{profile.min_sqm or 0}-{profile.max_sqm or 999}"
        if profile.requires_parking:
            params["parking"] = "1"
        if profile.requires_elevator:
            params["elevator"] = "1"
        if profile.requires_balcony:
            params["balcony"] = "1"

    return params


def _parse_item(item: dict[str, Any]) -> RawListing | None:
    """Map one feed item to a RawListing, defensively."""
    if item.get("type") in {"platinum", "kingdom"}:
        return None  # sponsored / aggregated cards

    raw_id = item.get("id") or item.get("ad_number") or item.get("link_token")
    if raw_id is None:
        return None
    source_id = str(raw_id)

    link_token = item.get("link_token") or source_id
    url = f"https://www.yad2.co.il/item/{link_token}"

    coords = item.get("coordinates") or {}
    lat = coords.get("latitude") if isinstance(coords, dict) else None
    lng = coords.get("longitude") if isinstance(coords, dict) else None

    posted_raw = item.get("date_added") or item.get("date")
    posted_at: datetime | None = None
    if isinstance(posted_raw, str):
        try:
            posted_at = datetime.fromisoformat(posted_raw.replace("Z", "+00:00"))
        except ValueError:
            posted_at = None

    street = item.get("street")
    house_no = item.get("address_number") or item.get("house_number")
    address = " ".join(p for p in [street, str(house_no) if house_no else None] if p) or None

    return RawListing(
        source=Source.YAD2,
        source_id=source_id,
        url=url,
        title=item.get("title") or item.get("row_1"),
        price=_safe_int(item.get("price")),
        rooms=_safe_float(item.get("rooms")),
        sqm=_safe_int(item.get("square_meters") or item.get("square_meter")),
        floor=_safe_int(item.get("floor")),
        total_floors=_safe_int(item.get("total_floors")),
        address=address,
        city=item.get("city"),
        neighborhood=item.get("neighborhood"),
        lat=_safe_float(lat),
        lng=_safe_float(lng),
        images=list(item.get("images") or []),
        posted_at=posted_at,
        raw=item,
    )


def _safe_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)  # type: ignore[call-overload,no-any-return]
    except (TypeError, ValueError):
        return None


def _safe_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class Yad2Scraper(BaseScraper):
    source = Source.YAD2

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            http2=True,
            timeout=get_settings().request_timeout_seconds,
        )

    async def search(self, area: Area, profile: SearchProfile | None = None) -> list[RawListing]:
        params = _build_params(area, profile)
        headers = _build_headers()

        logger.info(
            "yad2.search",
            area=area.name,
            params={k: v for k, v in params.items() if k != "mainland-device-id"},
        )
        response = await self._client.get(_FEED_URL, params=params, headers=headers)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()

        items = (
            payload.get("data", {}).get("feed", {}).get("feed_items")
            or payload.get("feed", {}).get("feed_items")
            or []
        )

        listings: list[RawListing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            parsed = _parse_item(item)
            if parsed is not None:
                listings.append(parsed)
        return listings

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
