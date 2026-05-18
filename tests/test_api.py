"""Smoke tests against the FastAPI app via httpx ASGI transport."""

from __future__ import annotations

import httpx
import pytest

from home_seek.api.app import create_app
from home_seek.db.seed import seed_all
from home_seek.db.session import Database, init_db


@pytest.mark.asyncio
async def test_health_endpoint(database: Database) -> None:
    await init_db()
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["telegram_configured"] is False  # not configured in tests
    assert payload["live_scrapers_enabled"] is False


@pytest.mark.asyncio
async def test_areas_listing_returns_seed_data(database: Database) -> None:
    await seed_all(reset=False)
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/areas")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert any(a["name"] == "פלורנטין" for a in body)


@pytest.mark.asyncio
async def test_dashboard_html_renders(database: Database) -> None:
    await seed_all(reset=False)
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "home-seek" in resp.text
    assert "פלורנטין" in resp.text


@pytest.mark.asyncio
async def test_create_and_delete_area_via_api(database: Database) -> None:
    await init_db()
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create
        resp = await client.post(
            "/api/areas",
            json={
                "name": "אזור בדיקה",
                "city": "תל אביב",
                "geometry_type": "radius",
                "center_lat": 32.0,
                "center_lng": 34.7,
                "radius_meters": 500,
            },
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        # Read
        resp = await client.get(f"/api/areas/{new_id}")
        assert resp.status_code == 200

        # Delete
        resp = await client.delete(f"/api/areas/{new_id}")
        assert resp.status_code == 204

        # 404 after delete
        resp = await client.get(f"/api/areas/{new_id}")
        assert resp.status_code == 404
