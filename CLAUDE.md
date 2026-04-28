# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a **planning-stage** repository. Source code is not yet implemented — the repo currently contains only specification documents:

- `PRD.md` — full product requirements (architecture, data model, endpoints, features)
- `TASKS.md` — granular implementation plan, ordered by stage with explicit dependencies (`→ #N`)
- `CLAUDE_PROMPT.md` — per-task prompt templates the user feeds in at session start
- `DESIGN-apple.md`, `DESIGN-notion.md` — visual design references for two distinct UI surfaces
- `.env.example` — canonical list of environment variables (don't invent new ones; add to this file)

When starting work, **read `PRD.md` and the relevant section of `TASKS.md` first**. Do not implement features that are not in a numbered task. The user works task-by-task — they will reference tasks by number (e.g. "выполни 1.5").

## Layered task model (critical)

Every task in `TASKS.md` is tagged with exactly one layer. **Do not mix layers in one change.**

| Tag | Layer | Scope |
|-----|-------|-------|
| 🔧 BE | Backend | API, DB, services, tests. No frontend. |
| ⚙️ FE-F | Frontend functional | Logic + base shadcn/ui only. **No visual styling.** |
| 🎨 FE-V | Frontend visual | Styles only — Apple HIG (dashboard) or Notion (tables/journal). **Do not touch logic, JSX structure, handlers, or API calls.** Diff must be CSS/classes only. |
| 🚀 INFRA | DevOps | Docker, Nginx, scripts, deploy. |

FE-F must ship before FE-V for the same feature. FE-V is a pure restyle pass over working FE-F code.

## Definition of Done (per layer)

These are the user's hard acceptance criteria — verify before claiming a task done. Full text in `PRD.md` §17.3.

- **BE**: endpoint visible in Swagger; ≥1 pytest happy path; Pydantic schemas defined; Alembic migration applies cleanly; logging on critical ops.
- **FE-F**: all four states handled (loading / error / empty / success); strict TypeScript (no `any`); responsive from 360px; data fetched via TanStack Query; only un-customized shadcn/ui components.
- **FE-V**: matches the assigned style (Apple HIG or Notion); both light + dark themes; skeleton loaders to prevent layout shift; logic diff is empty.

## Architecture

### Stack
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, httpx, APScheduler, python-jose, bcrypt
- **Database:** PostgreSQL 16 + **TimescaleDB** — `weather_daily` and `weather_forecast` are hypertables; continuous aggregates for week/month/season rollups; compression policy after 1 year
- **Frontend:** React 18 + TypeScript (strict), Vite, Tailwind, shadcn/ui, Recharts (default) + Plotly (heatmap/correlations), TanStack Query, Zustand, React Router v6
- **Telegram:** python-telegram-bot, runs as separate Docker service
- **Infra:** Docker Compose, Nginx, Let's Encrypt

### Backend layout (target — see `PRD.md` §12)
```
backend/app/
├── api/              # FastAPI routers
├── core/             # config, security, JWT
├── db/               # models, async session
├── services/
│   ├── weather/      # open_meteo, nasa_power, openweathermap clients
│   ├── analytics/    # calculators (GDD, VPD), anomalies, correlations
│   ├── alerts/       # rule engine
│   ├── reports/      # PDF (WeasyPrint/ReportLab)
│   └── backup/       # pg_dump → Yandex.Disk WebDAV
├── scheduler/        # APScheduler jobs
└── telegram_bot/
```

### Data model essentials
- `weather_daily` PRIMARY KEY = `(time, location_id, source)` — **same date stored once per source**, averaging is computed on read, not on write. `source ∈ {open_meteo, nasa_power, openweathermap}`.
- `VPD` is computed at ingest and stored. `GDD` is computed on read using the crop's `base_temperature` (per-crop, e.g. tomatoes=10°C, cucumbers=15°C, cabbage=4°C).
- History backfill = 10+ years per location, run as a FastAPI background task chunked by year (API rate limits). Track `Location.import_status` and `import_progress`. **Use UPSERT** so retries are idempotent.
- The unified read endpoint `GET /api/weather/daily` accepts `source=average` and computes the mean across available sources on the fly.

### Scheduler jobs (MSK)
- 03:00 — fetch yesterday's data (all sources, all locations)
- 06:00, 18:00 — refresh forecast
- hourly — evaluate alert rules
- 04:00 — `pg_dump` → gzip → Yandex.Disk WebDAV
- 1st of month — recompute climate normals

### Frontend visual split
Two coexisting style systems, applied per page:
- **Apple HIG** → Dashboard, Charts, Analytics (16–20px radius, layered shadows, Inter, system blue `#007AFF`, generous spacing)
- **Notion** → Tables, Journal, Settings, Alerts (minimal borders, dense layout, monospace numerics, sticky headers, hover row tint)

Do not cross-pollinate. Apple HIG cards do not appear on the journal page.

## Common commands

The user works through Docker Compose. Once `backend/`, `frontend/`, `docker-compose*.yml` exist:

```bash
# Dev (hot-reload)
docker compose -f docker-compose.dev.yml up -d

# Migrations
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "description"
docker compose exec backend alembic downgrade -1

# Seed (admin user, crops dictionary)
docker compose exec backend python -m app.scripts.seed

# Tests
docker compose exec backend pytest
docker compose exec backend pytest --cov=app --cov-report=html
docker compose exec backend pytest path/to/test_file.py::test_name   # single test

# Frontend type check
docker compose exec frontend pnpm tsc --noEmit

# DB shell
docker compose exec db psql -U weather -d weather

# Logs
docker compose logs -f backend
docker compose logs -f telegram_bot

# Restore from backup
docker compose exec backend python -m app.scripts.restore <backup_file>

# Production
docker compose -f docker-compose.prod.yml up -d
```

Frontend dev: http://localhost:5173 · Swagger: http://localhost:8000/api/docs

## Conventions enforced by the user

- **Python:** PEP 8, type hints everywhere, `async`/`await` for I/O, Pydantic v2 schemas for every endpoint.
- **TypeScript:** strict mode, no `any`. Generate types from OpenAPI or import from a shared module — do not duplicate by hand.
- **Secrets:** only via `.env` (template = `.env.example`). Never commit secrets. Never inline API keys.
- **Migrations:** always Alembic — no `Base.metadata.create_all` in app code.
- **Retry:** external API clients use `tenacity` with exponential backoff (3 attempts).
- **One commit per completed task** with a clear message.
- **Ask before implementing** if the task is ambiguous. Do not invent endpoints, fields, or features that aren't in the spec.

## Russian language

User writes in Russian. Specs (`PRD.md`, `TASKS.md`) are in Russian. Match the user's language when responding; keep code identifiers in English.
