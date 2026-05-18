"""Trigger the scrape pipeline ad-hoc (useful for the UI's 'Run now' button)."""

from __future__ import annotations

from fastapi import APIRouter

from home_seek.api.schemas import RunSummaryOut
from home_seek.pipeline.runner import run_once
from home_seek.scheduler.jobs import _registry  # internal helper, deliberate reuse

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run", response_model=RunSummaryOut)
async def trigger_run(dry_run: bool = False) -> RunSummaryOut:
    registry = _registry()
    summary = await run_once(registry=registry, dry_run=dry_run)
    return RunSummaryOut(
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        areas_processed=summary.areas_processed,
        listings_found=summary.listings_found,
        listings_new=summary.listings_new,
        notifications_sent=summary.notifications_sent,
        sources=summary.sources,
        errors=summary.errors,
    )
