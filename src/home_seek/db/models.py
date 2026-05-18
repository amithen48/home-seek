"""SQLAlchemy 2.0 ORM models - the entity map of the system.

Domain summary
--------------
- ``Area``           A named geographic region the user cares about. Either a
                    radius around a point, or an arbitrary polygon (GeoJSON).
- ``SearchProfile``  Per-area set of filtering criteria (price, rooms, etc.).
- ``Listing``        A scraped apartment, normalized across sources.
- ``Notification``   Audit log of every (listing, profile) we surfaced to the
                    user, so we never double-notify.
- ``ScrapeRun``      One execution of one scraper against one area, for
                    observability and circuit-breaker logic.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GeometryType(enum.StrEnum):
    """How an Area's footprint is described."""

    RADIUS = "radius"
    POLYGON = "polygon"


class Source(enum.StrEnum):
    """Listing source registry. Add a value here when adding a new scraper."""

    YAD2 = "yad2"
    MADLAN = "madlan"
    HOMELESS = "homeless"
    FACEBOOK = "facebook"
    STUB = "stub"  # synthetic data for development / tests


class ScrapeRunStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    BLOCKED = "blocked"  # 429 / 403 / captcha
    ERROR = "error"


class Furnished(enum.StrEnum):
    ANY = "any"
    YES = "yes"
    NO = "no"


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)

    geometry_type: Mapped[GeometryType] = mapped_column(
        Enum(GeometryType, name="geometry_type"), nullable=False
    )
    # Polygon variant: GeoJSON Polygon object stored as JSON.
    polygon_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    # Radius variant.
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Optional native-site identifiers - using these (when present) gives us a
    # much more targeted query than client-side polygon filtering.
    yad2_neighborhood_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    yad2_city_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yad2_area_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yad2_top_area_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    madlan_area_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profiles: Mapped[list[SearchProfile]] = relationship(
        back_populates="area",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="area",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    scrape_runs: Mapped[list[ScrapeRun]] = relationship(
        back_populates="area",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Area id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Search profiles
# ---------------------------------------------------------------------------


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    min_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_rooms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_rooms: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_sqm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_sqm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    requires_parking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_elevator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_balcony: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allows_pets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    furnished: Mapped[Furnished] = mapped_column(
        Enum(Furnished, name="furnished"), nullable=False, default=Furnished.ANY
    )

    floor_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Free-text OR filters applied against title + description.
    keywords_include: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    keywords_exclude: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    area: Mapped[Area] = relationship(back_populates="profiles", lazy="joined")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<SearchProfile id={self.id} area_id={self.area_id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable hash used for dedup across sources. See ``pipeline.dedup``.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    source: Mapped[Source] = mapped_column(Enum(Source, name="source"), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rooms: Mapped[float | None] = mapped_column(Float, nullable=True)
    sqm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)

    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    parking: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    elevator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    balcony: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    furnished: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pets_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    images_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    raw_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    notifications: Mapped[list[Notification]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Listing id={self.id} source={self.source.value} "
            f"price={self.price} rooms={self.rooms}>"
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("listing_id", "profile_id", name="uq_notification_listing_profile"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    area_id: Mapped[int] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    listing: Mapped[Listing] = relationship(back_populates="notifications", lazy="joined")
    area: Mapped[Area] = relationship(back_populates="notifications", lazy="joined")
    profile: Mapped[SearchProfile] = relationship(back_populates="notifications", lazy="joined")


# ---------------------------------------------------------------------------
# Scrape runs (observability)
# ---------------------------------------------------------------------------


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[Source] = mapped_column(Enum(Source, name="source"), nullable=False, index=True)
    area_id: Mapped[int | None] = mapped_column(
        ForeignKey("areas.id", ondelete="SET NULL"), nullable=True, index=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ScrapeRunStatus] = mapped_column(
        Enum(ScrapeRunStatus, name="scrape_run_status"),
        nullable=False,
        default=ScrapeRunStatus.RUNNING,
    )

    listings_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    listings_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notifications_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    area: Mapped[Area | None] = relationship(back_populates="scrape_runs", lazy="joined")
