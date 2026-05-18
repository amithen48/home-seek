"""Read endpoints for notifications and dismiss action."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from home_seek.api.schemas import NotificationOut
from home_seek.db.models import Notification
from home_seek.db.session import get_session

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    area_id: int | None = None,
    profile_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[Notification]:
    stmt = select(Notification).order_by(Notification.sent_at.desc())
    if area_id is not None:
        stmt = stmt.where(Notification.area_id == area_id)
    if profile_id is not None:
        stmt = stmt.where(Notification.profile_id == profile_id)
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())


@router.post(
    "/{notification_id}/dismiss",
    response_model=NotificationOut,
)
async def dismiss_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
) -> Notification:
    notif = await session.get(Notification, notification_id)
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
    notif.dismissed = True
    await session.flush()
    return notif
