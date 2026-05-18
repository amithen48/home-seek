"""CRUD endpoints for areas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.api.schemas import AreaCreate, AreaOut, AreaUpdate
from home_seek.db.models import Area
from home_seek.db.session import get_session

router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("", response_model=list[AreaOut])
async def list_areas(
    active: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Area]:
    stmt = select(Area).order_by(Area.name)
    if active is not None:
        stmt = stmt.where(Area.active.is_(active))
    return list((await session.scalars(stmt)).all())


@router.post("", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
async def create_area(
    payload: AreaCreate,
    session: AsyncSession = Depends(get_session),
) -> Area:
    area = Area(**payload.model_dump())
    session.add(area)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"area with name={payload.name!r} already exists",
        ) from exc
    await session.refresh(area)
    return area


@router.get("/{area_id}", response_model=AreaOut)
async def get_area(area_id: int, session: AsyncSession = Depends(get_session)) -> Area:
    area = await session.get(Area, area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="area not found")
    return area


@router.patch("/{area_id}", response_model=AreaOut)
async def update_area(
    area_id: int,
    payload: AreaUpdate,
    session: AsyncSession = Depends(get_session),
) -> Area:
    area = await session.get(Area, area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="area not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(area, key, value)
    await session.flush()
    return area


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(area_id: int, session: AsyncSession = Depends(get_session)) -> None:
    area = await session.get(Area, area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="area not found")
    await session.delete(area)
