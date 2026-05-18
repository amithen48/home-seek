"""Read endpoints for scrape run history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.api.schemas import ScrapeRunOut
from home_seek.db.models import ScrapeRun, Source
from home_seek.db.session import get_session

router = APIRouter(prefix="/scrape-runs", tags=["scrape-runs"])


@router.get("", response_model=list[ScrapeRunOut])
async def list_runs(
    source: Source | None = None,
    area_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[ScrapeRun]:
    stmt = select(ScrapeRun).order_by(ScrapeRun.started_at.desc())
    if source is not None:
        stmt = stmt.where(ScrapeRun.source == source)
    if area_id is not None:
        stmt = stmt.where(ScrapeRun.area_id == area_id)
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())
