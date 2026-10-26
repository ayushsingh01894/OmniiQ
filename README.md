# OmniIQ

**One Workspace. Data to Decisions.**

A unified workspace for data analytics, machine learning, document AI, and repeatable workflows.
See [`PROJECT_SPEC.md`](PROJECT_SPEC.md) for the full scope and
[`docs/implementation-status.md`](docs/implementation-status.md) for what exists today.

> **Status: Phases 1–2 complete (foundation, identity, Data Studio).** You can register, manage
> organizations/projects with roles, upload CSV/Excel files, inspect a data-quality profile, apply
> cleaning steps that create new dataset versions, and export results. Analytics, ML, Document AI and
> Workflow Studio are not built yet.

## Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Docker + Docker Compose v2 | recent | Option A (everything in containers) |
| Python | 3.12 | Option B (backend on host) |
| Node.js | 22+ | Option B (frontend on host) |
| PostgreSQL | 16 | Option B (or use only the `db` container) |
| Redis | 7 | Only if you run `JOB_BACKEND=celery` on the host; Docker includes it |

## Quick start (Option A: Docker)

```bash
make env          # creates .env from .env.example with a freshly generated SECRET_KEY
make up           # builds and starts db, backend, frontend
make migrate      # applies Alembic migrations
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/api/v1/docs
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready

Stop with `make down` (the database volume is kept).

Then open the frontend, choose **Create an account**, create a project, open it and upload a CSV or
Excel file (there is a sample in `sample_data/`).

## Running without Docker (Option B)

Start only the database container (`docker compose up -d db`) or use any local PostgreSQL 16,
then:

```bash
# backend
cp .env.example .env              # DATABASE_URL must point at your database
make backend-setup
cd backend && . .venv/bin/activate
set -a; . ../.env; set +a
alembic upgrade head
uvicorn app.main:app --reload

# frontend (new terminal)
make frontend-setup
cd frontend && npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## Checks

```bash
make test   # pytest + vitest (backend tests use SQLite; see docs/development.md for PostgreSQL)
make lint   # ruff + mypy + eslint + tsc
```

Backend tests use SQLite and need no database server. CI additionally applies migrations to a real
PostgreSQL service and runs the whole suite on it again.

## Layout

```
backend/    FastAPI app, Alembic migrations, tests
frontend/   React + TypeScript + Vite app
docs/       api.md, security.md, development.md, implementation-status.md
```

More folders from the spec (`ml/`, `sample_data/`, `scripts/`) are added when a phase needs them.

## Configuration

All configuration is via environment variables; see [`.env.example`](.env.example). `SECRET_KEY`
(at least 32 characters) is required and signs login tokens; `make env` generates one for you. Never
commit a real `.env`. Security details and limitations: [`docs/security.md`](docs/security.md).

## Known limitations

See [`docs/implementation-status.md`](docs/implementation-status.md).
