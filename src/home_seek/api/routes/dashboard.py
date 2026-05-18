"""HTML routes - rendered by Jinja2, interactive via HTMX."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek import __version__
from home_seek.config import get_settings
from home_seek.db.models import (
    Area,
    Listing,
    Notification,
    ScrapeRun,
    SearchProfile,
    Source,
)
from home_seek.db.session import get_session

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "templates"

router = APIRouter(tags=["html"], default_response_class=HTMLResponse)
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _base_context(request: Request, **extra: Any) -> dict[str, Any]:
    settings = get_settings()
    return {
        "request": request,
        "version": __version__,
        "settings": settings,
        "now_label": "live",
        **extra,
    }


@router.get("/", name="home")
async def home_page(request: Request, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    total_listings = await session.scalar(select(func.count(Listing.id))) or 0
    active_areas = (
        await session.scalar(select(func.count(Area.id)).where(Area.active.is_(True))) or 0
    )
    notifications_count = await session.scalar(select(func.count(Notification.id))) or 0

    by_source_rows = (
        await session.execute(
            select(Listing.source, func.count(Listing.id)).group_by(Listing.source)
        )
    ).all()
    by_source = {src.value: cnt for src, cnt in by_source_rows}

    recent_listings = list(
        (
            await session.scalars(select(Listing).order_by(Listing.first_seen_at.desc()).limit(10))
        ).all()
    )
    recent_runs = list(
        (
            await session.scalars(select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(8))
        ).all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _base_context(
            request,
            stats={
                "total_listings": total_listings,
                "active_areas": active_areas,
                "notifications": notifications_count,
                "by_source": by_source,
            },
            recent_listings=recent_listings,
            recent_runs=recent_runs,
            page="dashboard",
        ),
    )


@router.get("/areas", name="areas_page")
async def areas_page(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    areas = list((await session.scalars(select(Area).order_by(Area.name))).all())
    return templates.TemplateResponse(
        request,
        "areas.html",
        _base_context(request, areas=areas, page="areas"),
    )


@router.get("/profiles", name="profiles_page")
async def profiles_page(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    profiles = list(
        (
            await session.scalars(
                select(SearchProfile).order_by(SearchProfile.area_id, SearchProfile.name)
            )
        ).all()
    )
    areas = list((await session.scalars(select(Area).order_by(Area.name))).all())
    return templates.TemplateResponse(
        request,
        "profiles.html",
        _base_context(request, profiles=profiles, areas=areas, page="profiles"),
    )


@router.get("/listings", name="listings_page")
async def listings_page(
    request: Request,
    source: Source | None = None,
    city: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    stmt = select(Listing).order_by(Listing.first_seen_at.desc()).limit(200)
    if source is not None:
        stmt = stmt.where(Listing.source == source)
    if city is not None:
        stmt = stmt.where(Listing.city == city)
    listings = list((await session.scalars(stmt)).all())
    cities = list(
        (
            await session.scalars(select(Listing.city).where(Listing.city.is_not(None)).distinct())
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "listings.html",
        _base_context(
            request,
            listings=listings,
            cities=cities,
            sources=list(Source),
            selected_source=source,
            selected_city=city,
            page="listings",
        ),
    )


@router.get("/notifications", name="notifications_page")
async def notifications_page(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    notifs = list(
        (
            await session.scalars(
                select(Notification).order_by(Notification.sent_at.desc()).limit(100)
            )
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "notifications.html",
        _base_context(request, notifications=notifs, page="notifications"),
    )


@router.get("/runs", name="runs_page")
async def runs_page(request: Request, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    runs = list(
        (
            await session.scalars(
                select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(100)
            )
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "runs.html",
        _base_context(request, runs=runs, page="runs"),
    )


# ---------------------------------------------------------------------------
# HTMX partial endpoints (form posts for inline create/delete from the UI).
# ---------------------------------------------------------------------------


@router.post("/areas/{area_id}/delete", status_code=status.HTTP_303_SEE_OTHER)
async def delete_area_via_form(
    area_id: int, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    area = await session.get(Area, area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await session.delete(area)
    return HTMLResponse("", headers={"HX-Redirect": "/areas"})


@router.post("/profiles/{profile_id}/delete", status_code=status.HTTP_303_SEE_OTHER)
async def delete_profile_via_form(
    profile_id: int, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await session.delete(profile)
    return HTMLResponse("", headers={"HX-Redirect": "/profiles"})
