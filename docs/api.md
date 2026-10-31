# API reference (Phase 2B)

Interactive docs (generated from the code, always current): `http://localhost:8000/api/v1/docs`.

Base path `/api/v1`. Authenticated routes need `Authorization: Bearer <access_token>`.

## Errors

Every error has the same shape:

```json
{ "error": { "code": "project_name_taken", "message": "…", "details": [{"field": "name", "message": "…"}] } }
```

`details` appears only on `422 validation_error`.

| Status | Meaning |
| --- | --- |
| 401 | Missing/invalid/expired token, or bad credentials |
| 403 | You belong to the organization but your role is too low |
| 404 | Doesn't exist **or** you are not a member (indistinguishable on purpose) |
| 409 | Conflict (email taken, project name taken, already a member) |
| 422 | Validation failed |
| 413 | File too large |
| 415 | Unsupported file type |
| 429 | Rate limited (see `Retry-After`) |
| 503 | Background job queue unavailable (the job is recorded as failed) |

## Endpoints

| Method & path | Min. role | Notes |
| --- | --- | --- |
| `POST /auth/register` | – | 201. Also creates a personal organization you own |
| `POST /auth/login` | – | Returns `{access_token, token_type, expires_in}` |
| `GET /auth/me` | any user | Current user |
| `GET /organizations` | any user | Only organizations you belong to, with your role |
| `POST /organizations` | any user | You become owner |
| `GET /organizations/{id}/members` | viewer | |
| `POST /organizations/{id}/members` | admin | Body `{email, role}`; granting admin/owner needs owner |
| `GET /projects` | viewer | `?organization_id=&limit=1..100&offset=` → `{items,total,limit,offset}` |
| `POST /projects` | member | Body `{organization_id, name, description?}` |
| `GET /projects/{id}` | viewer | |
| `PATCH /projects/{id}` | member | Only supplied fields change; `description: null` clears it |
| `DELETE /projects/{id}` | admin | 204 |
| `GET /health/live`, `/health/ready` | – | Phase 1 |

### Datasets and jobs

Long-running work returns **202** with a job; poll `GET /jobs/{id}` until `status` is `succeeded`,
`failed` or `cancelled` (`queued` and `running` are the non-terminal states). `progress` is 0–100.

| Method & path | Min. role | Notes |
| --- | --- | --- |
| `POST /projects/{id}/datasets` | member | `multipart/form-data`: `file` (.csv/.xlsx), optional `name`. 202 → `{dataset, job}` |
| `GET /projects/{id}/datasets` | viewer | `?limit=1..100&offset=` → `{items,total,limit,offset}` |
| `GET /datasets/{id}` | viewer | Dataset + all `versions` (schema, row counts, checksum, the operations that produced each) |
| `DELETE /datasets/{id}` | admin | Removes versions, jobs and stored files. 204 |
| `GET /datasets/{id}/preview` | viewer | `?version=&limit=1..200&offset=`; default latest version |
| `GET /datasets/{id}/profile` | viewer | `?version=`; 404 `profile_not_ready` if none |
| `POST /datasets/{id}/profile` | member | Body `{version?}`; recompute in the background. 202 → job |
| `POST /datasets/{id}/cleaning-jobs` | member | Body `{base_version?, operations: [...]}` (1–50). 202 → job; success creates a **new version** |
| `GET /datasets/{id}/export` | viewer | `?version=&format=csv\|json`; attachment download |
| `GET /datasets/{id}/jobs` | viewer | Recent jobs, newest first |
| `GET /jobs/{id}` | viewer | Status, progress, `result`, sanitized `error_code`/`error_message` |
| `POST /jobs/{id}/cancel` | member | Only a still-`queued` job; otherwise 409 |

Cleaning operations (`op`): `drop_duplicates {subset?, keep}`, `drop_missing {columns?, how}`,
`fill_missing {column, strategy: mean\|median\|mode\|constant, value?}`, `drop_columns {columns}`,
`rename_column {column, new_name}`, `trim_whitespace {columns?}`,
`cast_type {column, to: integer\|float\|string\|boolean\|datetime}`. Unknown operations or extra
fields are rejected with 422. Datetimes are stored as naive UTC.

Not built yet: analytics queries and charts, organization update/delete, member removal/role change, token refresh, logout endpoint.
