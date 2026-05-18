"""Scraper interface every site-specific scraper must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from home_seek.db.models import Area, SearchProfile, Source


@dataclass(slots=True)
class RawListing:
    """The unified listing shape every scraper must return.

    Fields mirror ``db.models.Listing`` but exist independently so scrapers can
    be developed without an ORM session in scope.
    """

    source: Source
    source_id: str | None
    url: str
    title: str | None = None
    price: int | None = None
    rooms: float | None = None
    sqm: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    address: str | None = None
    city: str | None = None
    neighborhood: str | None = None
    lat: float | None = None
    lng: float | None = None
    parking: bool | None = None
    elevator: bool | None = None
    balcony: bool | None = None
    furnished: bool | None = None
    pets_allowed: bool | None = None
    description: str | None = None
    images: list[str] = field(default_factory=list)
    contact_name: str | None = None
    contact_phone: str | None = None
    posted_at: datetime | None = None
    raw: dict[str, object] | None = None


class BaseScraper(ABC):
    """All scrapers implement search(); ``fetch_details`` is optional."""

    source: Source

    @abstractmethod
    async def search(self, area: Area, profile: SearchProfile | None = None) -> list[RawListing]:
        """Return the latest listings for the given area (newest first).

        Profile is optional: scrapers MAY push price/rooms filters into the
        upstream query for efficiency. Final filtering still happens in
        ``pipeline.filter``.
        """

    async def fetch_details(self, listing: RawListing) -> RawListing:
        """Optional second-pass enrichment - default no-op."""
        return listing


class ScraperRegistry:
    """Process-wide registry mapping ``Source`` -> scraper instance."""

    def __init__(self) -> None:
        self._by_source: dict[Source, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        self._by_source[scraper.source] = scraper

    def get(self, source: Source) -> BaseScraper:
        if source not in self._by_source:
            raise KeyError(f"No scraper registered for source={source.value!r}")
        return self._by_source[source]

    def all(self) -> list[BaseScraper]:
        return list(self._by_source.values())

    def __contains__(self, source: Source) -> bool:
        return source in self._by_source


scrapers = ScraperRegistry()
