"""Pydantic v2 request / response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from home_seek.db.models import (
    Furnished,
    GeometryType,
    ScrapeRunStatus,
    Source,
)

# ---------------------------------------------------------------------------
# Area
# ---------------------------------------------------------------------------


class AreaBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    city: Annotated[str, Field(min_length=1, max_length=80)]
    geometry_type: GeometryType
    polygon_json: dict[str, object] | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    radius_meters: int | None = None
    yad2_neighborhood_ids: list[int] | None = None
    yad2_city_id: int | None = None
    yad2_area_id: int | None = None
    yad2_top_area_id: int | None = None
    madlan_area_slug: str | None = None
    active: bool = True


class AreaCreate(AreaBase):
    pass


class AreaUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    geometry_type: GeometryType | None = None
    polygon_json: dict[str, object] | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    radius_meters: int | None = None
    yad2_neighborhood_ids: list[int] | None = None
    yad2_city_id: int | None = None
    yad2_area_id: int | None = None
    yad2_top_area_id: int | None = None
    madlan_area_slug: str | None = None
    active: bool | None = None


class AreaOut(AreaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Search profile
# ---------------------------------------------------------------------------


class SearchProfileBase(BaseModel):
    area_id: int
    name: Annotated[str, Field(min_length=1, max_length=120)]
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: float | None = None
    max_rooms: float | None = None
    min_sqm: int | None = None
    max_sqm: int | None = None
    requires_parking: bool = False
    requires_elevator: bool = False
    requires_balcony: bool = False
    allows_pets: bool = False
    furnished: Furnished = Furnished.ANY
    floor_min: int | None = None
    floor_max: int | None = None
    keywords_include: list[str] | None = None
    keywords_exclude: list[str] | None = None
    active: bool = True


class SearchProfileCreate(SearchProfileBase):
    pass


class SearchProfileUpdate(BaseModel):
    name: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: float | None = None
    max_rooms: float | None = None
    min_sqm: int | None = None
    max_sqm: int | None = None
    requires_parking: bool | None = None
    requires_elevator: bool | None = None
    requires_balcony: bool | None = None
    allows_pets: bool | None = None
    furnished: Furnished | None = None
    floor_min: int | None = None
    floor_max: int | None = None
    keywords_include: list[str] | None = None
    keywords_exclude: list[str] | None = None
    active: bool | None = None


class SearchProfileOut(SearchProfileBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fingerprint: str
    source: Source
    source_id: str | None
    url: str
    title: str | None
    price: int | None
    rooms: float | None
    sqm: int | None
    floor: int | None
    total_floors: int | None
    address: str | None
    city: str | None
    neighborhood: str | None
    lat: float | None
    lng: float | None
    parking: bool | None
    elevator: bool | None
    balcony: bool | None
    furnished: bool | None
    pets_allowed: bool | None
    description: str | None
    images_json: list[str] | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    listing_id: int
    area_id: int
    profile_id: int
    sent_at: datetime
    telegram_message_id: int | None
    dismissed: bool


# ---------------------------------------------------------------------------
# Scrape run
# ---------------------------------------------------------------------------


class ScrapeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: Source
    area_id: int | None
    started_at: datetime
    finished_at: datetime | None
    status: ScrapeRunStatus
    listings_found: int
    listings_new: int
    notifications_sent: int
    error_message: str | None


# ---------------------------------------------------------------------------
# Pipeline trigger
# ---------------------------------------------------------------------------


class RunSummaryOut(BaseModel):
    started_at: datetime
    finished_at: datetime | None
    areas_processed: int
    listings_found: int
    listings_new: int
    notifications_sent: int
    sources: list[Source]
    errors: list[str]


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str
    telegram_configured: bool
    live_scrapers_enabled: bool
