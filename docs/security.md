# Security notes

Status: **Phase 2B (identity, access control, dataset uploads, background jobs)**. This is not a security audit; a full review is
planned for Phase 7. Everything below describes what is implemented and tested today, and what is not.

## Implemented

| Area | What exists | Where |
| --- | --- | --- |
| Password storage | Argon2id (argon2-cffi defaults), salted; plaintext never stored or logged | `core/security.py` |
| Password rules | 10–128 characters (length only; no breach-list check yet) | `schemas/auth.py` |
| Login | Unknown email and wrong password return the identical 401 body, and a dummy hash is verified for unknown emails to even out timing | `services/auth.py` |
| Tokens | Signed JWT (HS256), 30 min expiry by default, `sub` + `exp` required; tampered/expired/unknown-user tokens → 401 | `core/security.py`, `api/deps.py` |
| Secrets | `SECRET_KEY` (≥ 32 chars) has no default; the app refuses to start without it | `core/config.py` |
| Authorization | Server-side on every organization/project route; roles viewer < member < admin < owner | `services/access.py` |
| IDOR | Non-members get **404** (not 403) for organizations and projects, identical to "does not exist" | `services/access.py`, `tests/test_authorization.py` |
| Role granting | Admins may grant member/viewer only; only owners may grant admin/owner | `services/access.py` |
| Rate limiting | Login: 10 attempts / 60 s per IP+email. Register: 5 / hour per IP. Returns 429 + `Retry-After` | `core/rate_limit.py` |
| Error handling | One error shape; validation errors contain field + message only, **never the submitted value** (so passwords are not echoed) | `core/errors.py` |
| Audit log | register, login (success and failure), organization create, member add, project create/update/delete. Details never include passwords or tokens | `services/audit.py` |
| SQL | SQLAlchemy ORM only; no string-built SQL | all services |
| Containers | Backend image runs as a non-root user; Postgres/backend/frontend ports bound to 127.0.0.1 in Compose | `backend/Dockerfile`, `docker-compose.yml` |

### Permission matrix (per organization)

| Action | viewer | member | admin | owner |
| --- | :-: | :-: | :-: | :-: |
| List members, read/list projects | ✓ | ✓ | ✓ | ✓ |
| Create / edit projects | | ✓ | ✓ | ✓ |
| Delete projects | | | ✓ | ✓ |
| Add members (member, viewer) | | | ✓ | ✓ |
| Add members (admin, owner) | | | | ✓ |

## Data uploads, storage and jobs (Phase 2B)

| Area | What exists | Where |
| --- | --- | --- |
| Upload validation | Extension allow-list (`.csv`, `.xlsx`); content **signature** checked (xlsx must be a zip containing `xl/workbook.xml`; CSV must be UTF-8 with no NUL bytes); empty files refused | `services/datasets/ingest.py` |
| Size limits | Upload size (default 25 MB) enforced while streaming, plus an early `Content-Length` check; row (500k) and column (500) caps; spreadsheet uncompressed-size cap (200 MB) against zip bombs | `service.py`, `ingest.py`, `api/v1/datasets.py` |
| XML safety | `openpyxl` runs with `defusedxml` (verified at runtime: `DEFUSEDXML=True`) | dependency |
| Private storage | Files live under `STORAGE_ROOT` (owner-only permissions), never served statically. Keys are generated from UUIDs; the user's filename is display-only. Keys are validated and resolved paths must stay inside the root (traversal, absolute paths, symlinks tested). Writes are atomic | `storage/local.py` |
| Originals untouched | The upload is stored as-is with its SHA-256; all processing writes **new** Parquet versions | `jobs.py` |
| Authorization | Every dataset/job route resolves access through the project's organization; outsiders get 404; viewers read, members change, admins delete | `services/access.py`, `tests/test_dataset_authorization.py` |
| Jobs | Claimed with a conditional `UPDATE` (a job cannot run twice, e.g. on broker redelivery); every outcome ends in a terminal state; unexpected errors are logged server-side and users see a generic message; user-facing errors never include cell values | `jobs.py` |
| Resource limits | Celery soft/hard time limits; jobs stuck in `running` after a worker death are failed at worker start | `workers/celery_app.py` |
| Queue outage | If the broker is down the job is marked failed (`enqueue_failed`) and the API returns 503 instead of leaving a job queued forever | `service.py` |
| Cleaning | A fixed, validated set of operations (no code execution); unknown fields and operations are rejected | `schemas/cleaning.py` |
| Rate limits | Per user on upload, cleaning and profile requests (30/min default) | `api/v1/datasets.py` |
| Deletion | Dataset/project deletion removes database rows first, then stored files (a failure leaves an orphan file, never a dangling row); delete is audited | `service.py` |
| Export | `Content-Disposition: attachment`, `nosniff`, `no-store`; sanitized filename; audited | `api/v1/datasets.py` |

## Known limitations (honest list)

- **CSV export is not protected against spreadsheet formula injection.** A cell such as `=HYPERLINK(...)`
  in uploaded data is exported unchanged (altering data silently would break reproducibility). Warn
  users before opening exports from untrusted data in Excel.
- **Files are not encrypted at rest** and live on one machine; there is no virus scanning.
- **Whole files are processed in memory** (bounded by the 25 MB / 500k-row limits). Large-data
  streaming is future work.
- **The framework buffers an upload body before our size check** when `Content-Length` is absent or
  false (chunked requests). Put a body-size limit on the reverse proxy in any real deployment.
- **A cancelled/failed ingest leaves the original file in storage** (by design: it is kept so the
  upload can be inspected). Only deleting the dataset removes it.
- **No automatic retry of failed jobs.** Users re-run them; deterministic data errors would just fail
  again. (Automatic retries come with Workflow Studio.)
- **Only the first sheet of an Excel workbook is read.**
- **No cleaning preview/dry run yet:** results are visible only after the job creates a new version
  (which is cheap to discard, since versions are additive).


- **No server-side logout.** Tokens are stateless; "sign out" discards the token in the browser, but a
  stolen token stays valid until it expires (30 min). Revocation/refresh tokens are future work.
- **Token in `sessionStorage`.** Script injected into the page (XSS) could read it. httpOnly cookies
  with CSRF protection are a possible later hardening. The frontend renders no raw HTML.
- **Rate limiter is in-memory and per process.** With several workers or restarts the counts are not
  shared. A Redis-backed limiter is planned alongside the Redis work in Phase 2B.
- **Email enumeration is possible** through registration ("already exists") and through "add member"
  ("no user with that email"). Accepted for now; the latter is admin-only.
- **No email verification, password reset, MFA, or account lockout.**
- **Member removal and role changes are not implemented** (add-only), so a mistaken grant cannot be
  undone through the API yet.
- **No CSRF protection is needed today** (Bearer header, not cookies) but this changes if cookies
  are adopted.
- **API keys, upload validation and worker limits** belong to later phases and do not exist yet.
- `uvicorn --reload` and the Vite dev server in Compose are development settings, not production.
