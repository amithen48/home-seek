# home-seek

> Apartment rental alert system for Israel.

A multi-source apartment listing aggregator that scrapes Yad2, Madlan,
Homeless and other Israeli rental sites, filters by user-defined
geographic areas and criteria, and delivers real-time alerts to Telegram.

## Status

This is the empty `main` branch. The first real implementation lands via a
PR; see open pull requests on this repository.

## Local development

Once a feature branch is merged, the entry point is:

```bash
make install
uv run hs db seed
uv run hs serve
```

See the PR description for the full layout.
