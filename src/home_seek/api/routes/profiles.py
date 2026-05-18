"""CRUD endpoints for search profiles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.api.schemas import (
    SearchProfileCreate,
    SearchProfileOut,
    SearchProfileUpdate,
)
from home_seek.db.models import Area, SearchProfile
from home_seek.db.session import get_session

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[SearchProfileOut])
async def list_profiles(
    area_id: int | None = None,
    active: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[SearchProfile]:
    stmt = select(SearchProfile).order_by(SearchProfile.area_id, SearchProfile.name)
    if area_id is not None:
        stmt = stmt.where(SearchProfile.area_id == area_id)
    if active is not None:
        stmt = stmt.where(SearchProfile.active.is_(active))
    return list((await session.scalars(stmt)).all())


@router.post("", response_model=SearchProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: SearchProfileCreate,
    session: AsyncSession = Depends(get_session),
) -> SearchProfile:
    if await session.get(Area, payload.area_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"area_id={payload.area_id} does not exist",
        )
    profile = SearchProfile(**payload.model_dump())
    session.add(profile)
    await session.flush()
    return profile


@router.get("/{profile_id}", response_model=SearchProfileOut)
async def get_profile(
    profile_id: int, session: AsyncSession = Depends(get_session)
) -> SearchProfile:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return profile


@router.patch("/{profile_id}", response_model=SearchProfileOut)
async def update_profile(
    profile_id: int,
    payload: SearchProfileUpdate,
    session: AsyncSession = Depends(get_session),
) -> SearchProfile:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    await session.flush()
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: int, session: AsyncSession = Depends(get_session)) -> None:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    await session.delete(profile)
