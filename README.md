# home-seek

> Apartment rental alert system for Israel. Scrape multiple sites, filter by
> geographic areas, surface new listings in a small web dashboard and over
> Telegram. Python 3.13, FastAPI, SQLAlchemy 2, HTMX + Tailwind.

## Status

Phase 1 scaffolding is in place: full entity model, REST + HTML dashboard,
APScheduler-driven pipeline, stub scraper, seed data, and a Yad2 scraper
skeleton documented in [`docs/yad2_api_mapping.md`](docs/yad2_api_mapping.md).

Real Yad2/Madlan/Homeless scrapers are intentionally last — they need an
environment with outbound network access to those hosts before they can be
verified end-to-end.

## Layout

```
src/home_seek/
├── api/                FastAPI app + REST + HTML routes
├── db/                 SQLAlchemy 2 models, session, seed data
├── geo/                point-in-area helpers (radius + GeoJSON polygons)
├── notify/             Telegram dispatcher + message formatter
├── pipeline/           dedup, filter, end-to-end runner
├── scheduler/          APScheduler interval job
├── scrapers/           BaseScraper + StubScraper + Yad2 skeleton
├── web/                Jinja templates + static assets
├── cli.py              `hs` / `home-seek` Typer CLI
└── config.py           pydantic-settings (reads .env)
```

## Quick start

```bash
# install python 3.13 + project deps + dev tools
uv python install 3.13
make install

# seed the DB with a few areas, profiles, listings, runs and notifications
uv run hs db seed

# run the API + web dashboard at http://localhost:8000
uv run hs serve --reload

# run the pipeline once on demand (dry-run = no Telegram send)
uv run hs run --dry-run
```

## Development

All tooling lives in `pyproject.toml` — no `mypy.ini`, no `ruff.toml`.

```bash
make fmt         # auto-format + auto-fix
make lint        # ruff check --fix
make typecheck   # mypy --strict src/
make test        # pytest
make check       # everything, no writes
```

Install the pre-commit hook so `ruff fix` + `mypy` run before every commit:

```bash
make install-hooks
```

## Configuration

Copy `.env.example` to `.env`. Important flags:

| Variable | Effect |
|---|---|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | If both set, the notifier actually sends. Otherwise it logs and records a row in `notifications` without calling Telegram. |
| `SCHEDULER_ENABLED` | Whether the FastAPI lifespan starts the APScheduler loop. |
| `SCRAPE_INTERVAL_MINUTES` | How often `pipeline.runner.run_once()` fires. |
| `ENABLE_LIVE_SCRAPERS` | `false` (default) registers only `StubScraper`. `true` adds `Yad2Scraper`, which needs network access to `gw.yad2.co.il`. |

## Roadmap

- [x] Phase 1 — data model, REST + dashboard, scheduler, stub scraper.
- [ ] Phase 1.5 — verify Yad2 mapping live (see `docs/yad2_api_mapping.md`).
- [ ] Phase 2 — Madlan + Homeless scrapers.
- [ ] Phase 3 — Facebook ingest via browser extension (out-of-scope for now).
- [ ] Phase 4 — production deploy (Hetzner / Fly / Render).

## Notes on the dev environment used to build this

The remote container the initial scaffolding was built in has a restrictive
outbound network policy that blocks `*.yad2.co.il`, `api.telegram.org`,
`nominatim.openstreetmap.org` and similar. The system is therefore designed
to be useful without those endpoints (stub scraper, no-op Telegram notifier)
and to fail gracefully when they are unreachable.
