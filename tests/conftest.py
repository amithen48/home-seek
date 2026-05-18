"""Shared pytest fixtures.

We use an in-memory SQLite DB per test, wired through the same factory the
production code uses (``get_database``). To make that injection work without
patching imports everywhere, the fixtures override the ``DATABASE_URL``
environment variable and clear the lru_caches before the app reads them.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from home_seek.config import get_settings
from home_seek.db.session import Database, get_database, init_db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test gets its own SQLite file inside the pytest tmp dir."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("ENABLE_LIVE_SCRAPERS", "false")
    # Reset cached settings + db so the new env vars take effect.
    get_settings.cache_clear()
    get_database.cache_clear()


@pytest_asyncio.fixture
async def database() -> AsyncIterator[Database]:
    await init_db()
    db = get_database()
    try:
        yield db
    finally:
        await db.dispose()
        get_database.cache_clear()
        # Best-effort: remove the sqlite file so other tests don't see it.
        url = os.environ.get("DATABASE_URL", "")
        if url.startswith("sqlite+aiosqlite:///"):
            path = Path(url.removeprefix("sqlite+aiosqlite:///"))
            path.unlink(missing_ok=True)  # noqa: ASYNC240 - fixture teardown, never on hot path
