"""Top-level Typer CLI: ``hs <command>`` / ``home-seek <command>``."""

from __future__ import annotations

import asyncio

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from home_seek import __version__
from home_seek.config import get_settings
from home_seek.db.seed import seed_all
from home_seek.db.session import get_database, init_db
from home_seek.logging_setup import configure_logging
from home_seek.pipeline.runner import run_once
from home_seek.scrapers import StubScraper, scrapers
from home_seek.scrapers.base import ScraperRegistry

app = typer.Typer(
    name="home-seek",
    help="home-seek - apartment rental alert system.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Database utilities")
app.add_typer(db_app, name="db")

console = Console()


@app.callback()
def _bootstrap() -> None:
    configure_logging()


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"home-seek [bold]{__version__}[/bold]")


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------


@db_app.command("init")
def db_init() -> None:
    """Create all DB tables (idempotent)."""
    asyncio.run(init_db())
    console.print(":white_check_mark: tables created")


@db_app.command("seed")
def db_seed(
    reset: bool = typer.Option(False, "--reset", help="Drop all tables before seeding."),
) -> None:
    """Seed the DB with realistic sample data."""
    asyncio.run(seed_all(reset=reset))
    console.print(":seedling: seed data inserted")


@db_app.command("reset")
def db_reset() -> None:
    """DESTRUCTIVE: drop and recreate all tables."""

    async def _reset() -> None:
        db = get_database()
        await db.drop_all()
        await db.create_all()

    asyncio.run(_reset())
    console.print(":wastebasket:  tables dropped and recreated")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _build_default_registry() -> ScraperRegistry:
    settings = get_settings()
    scrapers._by_source.clear()
    scrapers.register(StubScraper())
    if settings.enable_live_scrapers:
        from home_seek.scrapers.yad2 import Yad2Scraper

        scrapers.register(Yad2Scraper())
    return scrapers


@app.command("run")
def run_pipeline(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--send",
        help="In dry-run mode, notifications are recorded but not sent over Telegram.",
    ),
    area_id: int | None = typer.Option(None, help="Limit to a single area id."),
) -> None:
    """Run the full pipeline once (scrape → dedup → filter → notify)."""
    registry = _build_default_registry()
    summary = asyncio.run(run_once(registry=registry, dry_run=dry_run, area_id=area_id))

    table = Table(title="run summary", header_style="bold")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("areas processed", str(summary.areas_processed))
    table.add_row("listings found", str(summary.listings_found))
    table.add_row("listings new", str(summary.listings_new))
    table.add_row("notifications sent", str(summary.notifications_sent))
    table.add_row("errors", str(len(summary.errors)))
    console.print(table)
    for err in summary.errors:
        console.print(f"[red]✗[/red] {err}")


# ---------------------------------------------------------------------------
# Web / API
# ---------------------------------------------------------------------------


@app.command("serve")
def serve(
    host: str = typer.Option(None, help="Override API host."),
    port: int = typer.Option(None, help="Override API port."),
    reload: bool = typer.Option(False, help="Enable uvicorn reload."),
) -> None:
    """Start the FastAPI server (Jinja dashboard + JSON API)."""
    settings = get_settings()
    uvicorn.run(
        "home_seek.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload or settings.api_reload,
    )


if __name__ == "__main__":
    app()
