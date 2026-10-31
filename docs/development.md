# Development guide

## Conventions

- Backend layering: `api/` (HTTP only) → `services/` (business logic and authorization, using
  SQLAlchemy sessions directly). A separate `repositories/` layer is deliberately not used yet; add it
  only if queries start being shared across services.
- Every organization- or project-scoped service function calls `services/access.py` first. New
  features must do the same and add a cross-organization test next to it.
- Schema changes go through Alembic: `cd backend && alembic revision -m "describe change"`, then
  edit the generated file. Migrations are never run automatically at app start; use `make migrate`.
- Frontend code is organised by feature under `frontend/src/features/<feature>/`; shared UI lives in
  `frontend/src/components/`. Server state goes through TanStack Query; API calls live in
  `frontend/src/lib/`.
- Unbuilt features are shown as disabled and labelled, never as working-looking controls.

## Background jobs

- `JOB_BACKEND=inline` (default outside Docker): the API runs a job right after sending its response.
  No Redis needed; fine for development and what the tests use.
- `JOB_BACKEND=celery` (Docker Compose): the API sends the job id to Redis and the `worker` service
  runs it. Start a worker on the host with
  `cd backend && celery -A app.workers.celery_app worker --loglevel=INFO`.
- Both paths call the same function, `services/datasets/jobs.py:execute_job`. New job types are added
  there, with a matching `JobType` enum value and tests that cover success, failure and idempotency.
- Jobs write results to the `data_jobs` table, not to Redis.

## Running the tests on PostgreSQL

The suite runs on in-memory SQLite by default. To run the identical tests on PostgreSQL, point
`TEST_DATABASE_URL` at an **empty, throw-away** database (the tests drop and recreate all tables):

```bash
createdb omniiq_test
TEST_DATABASE_URL=postgresql+psycopg://USER:PASS@localhost:5432/omniiq_test make backend-test
```

## Dependency pinning

Backend dependencies are pinned to exact versions in `backend/pyproject.toml`. Frontend dependencies
are pinned exactly in `package.json` with `package-lock.json` committed. Update deliberately and
re-run all checks.

## Useful commands

| Task | Command |
| --- | --- |
| Backend tests | `make backend-test` |
| Backend lint + types | `make backend-lint` |
| Frontend tests | `make frontend-test` |
| Frontend lint + types | `make frontend-lint` |
| Production frontend build | `cd frontend && npm run build` |
| New migration | `cd backend && alembic revision -m "message"` |
| Apply migrations | `make migrate` (Docker) or `cd backend && alembic upgrade head` |
