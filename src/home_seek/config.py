"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{PROJECT_ROOT / 'home_seek.db'}",
        description="Async SQLAlchemy URL (must use aiosqlite for sqlite).",
    )

    # Telegram
    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)

    # Scraping
    request_timeout_seconds: float = 20.0
    min_delay_between_requests_seconds: float = 30.0
    max_listings_per_run_per_area: int = 50
    user_agents_file: Path | None = None

    # Scheduler
    scrape_interval_minutes: int = 15
    scheduler_enabled: bool = True

    # API / Web
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"
    log_file: Path | None = None

    # Feature flags
    enable_live_scrapers: bool = Field(
        default=False,
        description=(
            "When False, the scheduler runs the stub scraper instead of hitting real "
            "external sites. Useful while the network policy blocks Israeli targets "
            "or during local development."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton settings instance."""
    return Settings()
