# Implementation status

_Last updated: end of Phase 2 (Phases 1, 2A and 2B together)._

| Phase | State |
| --- | --- |
| 1 — Foundation | Complete. Verified: tests, lint, types, real Postgres migrations. **Docker and CI never run** |
| 2A — Identity, organizations, projects | Complete and verified (also on real PostgreSQL) |
| 2B — Data Studio (upload, profile, clean, versions, export, jobs) | Complete and verified, including a real Celery worker + Redis + PostgreSQL run |
| 3 — Analytics Studio | Not started |
| 4–7 | Not started |

## What exists

**Foundation.** FastAPI app factory, environment-based settings (`DATABASE_URL`, `SECRET_KEY` required),
JSON logging, health endpoints (`/health/live`, `/health/ready`), SQLAlchemy 2 + Alembic (3 revisions),
React + TypeScript (strict) + Vite + Tailwind shell, Docker Compose (db, redis, backend, worker,
frontend), GitHub Actions workflow, Makefile.

**Identity (2A).** Register/login/`me`, Argon2 passwords, expiring tokens, organizations with roles
(viewer < member < admin < owner), member management (add), projects (CRUD, paginated), audit log,
rate limits on login/register, non-members get 404 on everything (no ID probing).

**Data Studio (2B).**
- *Upload:* `.csv` / `.xlsx`, extension **and** content-signature validated, size/row/column limits,
  original stored untouched with SHA-256, private storage with traversal protection.
- *Background jobs:* `queued → running → succeeded | failed | cancelled`, 202 + polling, progress,
  claim-once semantics, sanitized errors, time limits, stale-job recovery, visible failure when the
  queue is down. Runs inline (dev/tests) or on a Celery worker (Compose).
- *Ingest:* schema inference (integer/float/boolean/datetime/string), lossless ISO-date detection,
  normalized Parquet versions.
- *Profile:* rows/columns, duplicates, missing values, numeric/date statistics, top values, quality issues.
- *Cleaning:* 7 explicit operations (drop duplicates / missing, fill missing, drop / rename columns,
  trim whitespace, cast type); each run creates a **new version** and records the operations;
  failed steps create nothing and report which step failed without leaking values.
- *Preview* (paginated), *export* (CSV/JSON, authenticated download), *delete* (rows + files).
- *Frontend:* project page with upload and live job progress; dataset page with Preview, Profile,
  Clean (step builder), History tabs, version selector, export, role-aware controls, confirm-to-delete.
- *Sample data:* `sample_data/sales_sample.csv` (synthetic) with a test that proves its walkthrough works.

## Verified (actually executed)

Environment: Python 3.12, Node 22, **PostgreSQL 16 and Redis 7 installed in the sandbox**; no Docker.
Everything below was re-run from a fresh `git clone` of the final commit unless noted.

| Check | Result |
| --- | --- |
| Backend `pytest` on SQLite | **102 passed** |
| Same suite on **real PostgreSQL 16** (`TEST_DATABASE_URL`) | **102 passed** |
| `ruff` / `mypy --strict` | clean / no issues in 56 files |
| Migrations `0001→0003`: upgrade, downgrade, single head, **models == migrations** | pass (SQLite and PostgreSQL) |
| PostgreSQL column types (`uuid`, `timestamptz`, `json`, `boolean`) and role CHECK constraint | confirmed by inspecting the real database |
| Frontend `eslint` / `tsc` / `vitest` / production build | clean / clean / **58 passed** / succeeds |
| **Real end-to-end**: PostgreSQL + Redis + `celery worker` + uvicorn, driven with `curl` | register → upload CSV → job succeeded in the worker → clean job → version 2 → export shows cleaned data |
| **Queue outage** (Redis stopped, then upload) | HTTP 503 `job_queue_unavailable`; the job row is `failed / enqueue_failed` |
| Secret scan of tracked files | nothing found |
| **Mutation checks** — backend (7): dataset/job access ignoring membership, viewer allowed to upload, content-signature check off, job claim not conditional, storage traversal check removed, upload size limit removed | every mutation made a test fail; all reverted; suite green |
| **Mutation checks** — frontend (5): members may delete, viewers see the cleaning builder, multipart sent as JSON, no extension check, token missing on downloads | every mutation made a test fail; all reverted; suite green |

Bugs found *by* the tests/verification and fixed in this phase: job/dataset lists ordered randomly
when created within the same second (microsecond timestamps now); the "Created version N" message
vanished because the tab remounted (message now lives in the page); one wrongly-strict test
expectation; a weak test replaced by a deterministic one.

## NOT verified — please run these

- **`docker compose up --build`** and `make migrate`: no Docker in the sandbox. The compose file parses
  and the worker command/`celery_app` import were checked, but the images and the shared `storage`
  volume (file ownership for the non-root user) have never been built or started.
- **The GitHub Actions workflow** (YAML parses; never executed — including the new
  "run the suite again on PostgreSQL" step).
- **The UI in a real browser.** No screenshots were reviewed; component tests run in jsdom. Layout,
  responsiveness and file-picker behaviour in real browsers are unchecked.
- **Real `.xlsx` files produced by Excel/LibreOffice** (tests use files generated by pandas/openpyxl).
- **Large files and concurrency at scale** (limits are enforced and tested with small caps; real
  25 MB / 500k-row uploads and parallel workers were not load-tested).

First run on your machine:
```bash
make env && make up && make migrate
# http://localhost:5173 -> create account -> create project -> open it -> upload sample_data/sales_sample.csv
# watch the progress bar, then Profile -> Clean -> add the steps from sample_data/README.md -> Run
```
If your `.env` is older than Phase 2A it needs `SECRET_KEY=` (≥ 32 chars); `make env` makes a new one.

## Known issues / deviations

- Security limitations are listed honestly in `docs/security.md` (e.g. CSV export has no formula-injection
  protection, files are not encrypted at rest, uploads are processed in memory, no auto-retry of failed
  jobs, only the first Excel sheet is read, in-memory rate limiter, no server-side logout).
- No cleaning *preview* (dry run); no UI for creating organizations or managing members (API exists).
- Dataset and project lists show the first 50 only (the page says so); no pagination controls yet.
- Spec items deferred on purpose: `/datasets/{id}/query` (Phase 3), shadcn/ui (small hand-written
  components are used), MLflow, pgvector/FAISS (later phases).
- Starlette `TestClient` prints an `httpx` deprecation warning (harmless).
- Dependency versions are pinned to what resolved in the sandbox on the build date.

## Next: Phase 3 — Analytics Studio (awaiting approval)

Deterministic Pandas calculations only (no LLM-invented numbers): grouped summaries, correlations,
distributions, filters, KPI cards, charts (Recharts/Plotly), dashboard persistence, CSV/JSON export, and
a restricted, read-only, time- and resource-limited query capability. Before starting, please run the
"NOT verified" list above and send me anything that breaks.
