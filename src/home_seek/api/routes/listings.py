"""Read-only endpoints for listings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.api.schemas import ListingOut
from home_seek.db.models import Listing, Source
from home_seek.db.session import get_session

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=list[ListingOut])
async def list_listings(
    source: Source | None = None,
    city: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_rooms: float | None = None,
    max_rooms: float | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[Listing]:
    stmt = select(Listing).order_by(Listing.first_seen_at.desc())
    if source is not None:
        stmt = stmt.where(Listing.source == source)
    if city is not None:
        stmt = stmt.where(Listing.city == city)
    if min_price is not None:
        stmt = stmt.where(Listing.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.price <= max_price)
    if min_rooms is not None:
        stmt = stmt.where(Listing.rooms >= min_rooms)
    if max_rooms is not None:
        stmt = stmt.where(Listing.rooms <= max_rooms)
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, session: AsyncSession = Depends(get_session)) -> Listing:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return listing
