import hashlib
import uuid

import pandas as pd
from sqlalchemy import select

from app.models import AuditLog, DataJob, Dataset, DatasetVersion
from app.storage import get_storage
from tests.helpers import (
    SAMPLE_CSV,
    D,
    J,
    P,
    clean,
    make_project,
    ready_dataset,
    upload,
    xlsx_bytes,
)

# ---------- upload and ingestion ----------


def test_upload_returns_202_and_job_completes(client, make_actor):
    ana = make_actor("Ana")
    pid = make_project(client, ana)
    r = upload(client, ana, pid)
    assert r.status_code == 202
    body = r.json()
    assert body["dataset"]["status"] == "processing" and body["job"]["status"] == "queued"
    assert body["job"]["job_type"] == "ingest"

    job = client.get(f"{J}/{body['job']['id']}", headers=ana.headers).json()
    assert job["status"] == "succeeded" and job["progress"] == 100
    assert job["result"] == {"version": 1, "rows": 4, "columns": 5}

    ds = client.get(f"{D}/{body['dataset']['id']}", headers=ana.headers).json()
    assert ds["status"] == "ready" and ds["name"] == "sales"
    v1 = ds["latest_version"]
    assert (v1["version"], v1["row_count"], v1["column_count"]) == (1, 4, 5)
    assert {c["name"]: c["dtype"] for c in v1["columns"]} == {
        "id": "integer",
        "name": "string",
        "amount": "float",
        "joined": "datetime",
        "active": "string",
    }
    assert v1["columns"][1]["nullable"] is True


def test_original_file_is_stored_untouched_with_checksum(client, make_actor, db):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    ds = db.scalar(select(Dataset))
    assert ds.original_checksum_sha256 == hashlib.sha256(SAMPLE_CSV).hexdigest()
    assert ds.original_size_bytes == len(SAMPLE_CSV)
    with get_storage().open(ds.original_storage_key) as f:
        assert f.read() == SAMPLE_CSV
    assert str(did) in ds.original_storage_key and "sales" not in ds.original_storage_key


def test_preview_is_paginated_and_json_safe(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    r = client.get(f"{D}/{did}/preview", params={"limit": 2, "offset": 1}, headers=ana.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_rows"] == 4 and len(body["rows"]) == 2 and body["version"] == 1
    assert body["rows"][0]["amount"] is None  # NaN became null
    assert body["rows"][0]["joined"].startswith("2024-01-03")
    assert (
        client.get(f"{D}/{did}/preview", params={"limit": 201}, headers=ana.headers).status_code
        == 422
    )


def test_profile_is_computed_from_the_data(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    prof = client.get(f"{D}/{did}/profile", headers=ana.headers).json()
    assert prof["row_count"] == 4 and prof["duplicate_rows"] == 1
    cols = {c["name"]: c for c in prof["columns"]}
    assert cols["amount"]["missing"] == 2 and cols["amount"]["missing_pct"] == 50.0
    assert cols["amount"]["stats"]["min"] == 7 and cols["amount"]["stats"]["max"] == 10.5
    assert cols["name"]["missing"] == 1
    assert cols["joined"]["stats"]["min"].startswith("2024-01-02")
    assert cols["active"]["top_values"][0] == {"value": "yes", "count": 2}
    codes = {i["code"] for i in prof["issues"]}
    assert {"duplicate_rows", "high_missing"} <= codes


def test_profile_job_recomputes(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    r = client.post(f"{D}/{did}/profile", json={}, headers=ana.headers)
    assert r.status_code == 202
    job = client.get(f"{J}/{r.json()['id']}", headers=ana.headers).json()
    assert job["status"] == "succeeded" and job["result"]["version"] == 1
    assert (
        client.get(f"{D}/{did}/profile", params={"version": 9}, headers=ana.headers).status_code
        == 404
    )


def test_excel_upload_and_mixed_column_becomes_text(client, make_actor):
    ana = make_actor("Ana")
    df = pd.DataFrame({"a": [1, 2, 3], "mixed": [1, "x", 2.5]})
    _, did = ready_dataset(client, ana, content=xlsx_bytes(df), filename="book.xlsx")
    v = client.get(f"{D}/{did}", headers=ana.headers).json()["latest_version"]
    assert {c["name"]: c["dtype"] for c in v["columns"]} == {"a": "integer", "mixed": "string"}


# ---------- validation of uploads ----------


def _expect(client, ana, status, code, **kw):
    r = upload(client, ana, make_project(client, ana, kw.pop("pname", "P")), **kw)
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    return r


def test_rejects_unsupported_extension(client, make_actor):
    _expect(client, make_actor("Ana"), 415, "unsupported_file_type", filename="evil.exe")


def test_rejects_binary_content_with_csv_extension(client, make_actor):
    _expect(
        client, make_actor("Ana"), 422, "invalid_file_content", content=b"a,b\n\x00\x01\x02,3\n"
    )


def test_rejects_csv_content_with_xlsx_extension(client, make_actor):
    _expect(
        client,
        make_actor("Ana"),
        422,
        "invalid_file_content",
        filename="x.xlsx",
        content=SAMPLE_CSV,
    )


def test_rejects_zip_that_is_not_a_workbook(client, make_actor):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    _expect(
        client,
        make_actor("Ana"),
        422,
        "invalid_file_content",
        filename="x.xlsx",
        content=buf.getvalue(),
    )


def test_rejects_non_utf8_csv(client, make_actor):
    _expect(
        client,
        make_actor("Ana"),
        422,
        "invalid_file_content",
        content="a,b\nñ,2\n".encode("latin-1"),
    )


def test_rejects_empty_file(client, make_actor):
    _expect(client, make_actor("Ana"), 422, "empty_dataset", content=b"")


def test_rejects_oversized_upload_and_stores_nothing(client, make_actor, limits, db):
    limits(max_upload_bytes=2048)
    big = b"a,b\n" + b"1,2\n" * 2000
    _expect(client, make_actor("Ana"), 413, "file_too_large", content=big)
    assert db.scalar(select(Dataset)) is None


def test_workbook_that_expands_too_much_is_rejected(client, make_actor, limits):
    limits(max_xlsx_uncompressed_bytes=1024)
    df = pd.DataFrame({"a": range(200), "b": ["x" * 20] * 200})
    _expect(
        client, make_actor("Ana"), 413, "file_too_large", filename="x.xlsx", content=xlsx_bytes(df)
    )


def test_unparseable_csv_fails_the_job_without_leaking_content(client, make_actor, db):
    ana = make_actor("Ana")
    pid = make_project(client, ana)
    r = upload(client, ana, pid, content=b"a,b\n1,2\n3,4,5,SECRETVALUE,6\n")
    job = client.get(f"{J}/{r.json()['job']['id']}", headers=ana.headers).json()
    assert job["status"] == "failed" and job["error_code"] == "unreadable_file"
    assert "SECRETVALUE" not in str(job)
    assert (
        client.get(f"{D}/{r.json()['dataset']['id']}", headers=ana.headers).json()["status"]
        == "failed"
    )


def test_too_many_rows_fails_the_job(client, make_actor, limits):
    limits(max_dataset_rows=3)
    ana = make_actor("Ana")
    r = upload(client, ana, make_project(client, ana))
    job = client.get(f"{J}/{r.json()['job']['id']}", headers=ana.headers).json()
    assert job["status"] == "failed" and job["error_code"] == "too_many_rows"


def test_duplicate_column_names_are_rejected(client, make_actor):
    ana = make_actor("Ana")
    r = upload(client, ana, make_project(client, ana), content=b"a, a\n1,2\n")
    job = client.get(f"{J}/{r.json()['job']['id']}", headers=ana.headers).json()
    assert job["status"] == "failed" and job["error_code"] == "duplicate_columns"


def test_dataset_names_unique_per_project(client, make_actor):
    ana = make_actor("Ana")
    p1, p2 = make_project(client, ana, "P1"), make_project(client, ana, "P2")
    assert upload(client, ana, p1, name="Sales").status_code == 202
    dup = upload(client, ana, p1, name="Sales")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "dataset_name_taken"
    assert upload(client, ana, p2, name="Sales").status_code == 202


def test_failed_name_conflict_leaves_no_orphan_file(client, make_actor, db):
    ana = make_actor("Ana")
    pid = make_project(client, ana)
    upload(client, ana, pid, name="Sales")
    storage = get_storage()
    before = {d.original_storage_key for d in db.scalars(select(Dataset))}
    upload(client, ana, pid, name="Sales")
    assert {d.original_storage_key for d in db.scalars(select(Dataset))} == before
    assert all(storage.exists(k) for k in before)


# ---------- cleaning and versions ----------


CLEAN_OPS = [
    {"op": "drop_duplicates"},
    {"op": "trim_whitespace", "columns": ["name"]},
    {"op": "fill_missing", "column": "amount", "strategy": "mean"},
    {"op": "fill_missing", "column": "name", "strategy": "constant", "value": "unknown"},
    {"op": "cast_type", "column": "active", "to": "boolean"},
]


def test_cleaning_creates_new_version_and_keeps_the_old_one(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    job = clean(client, ana, did, CLEAN_OPS)
    assert job["status"] == "succeeded", job
    assert job["result"]["version"] == 2 and job["result"]["rows_before"] == 4
    assert job["result"]["rows_after"] == 3 and len(job["result"]["steps"]) == 5

    ds = client.get(f"{D}/{did}", headers=ana.headers).json()
    assert [v["version"] for v in ds["versions"]] == [1, 2]
    v2 = ds["versions"][1]
    assert v2["parent_version"] == 1 and v2["row_count"] == 3
    assert v2["operations"][2] == {
        "op": "fill_missing",
        "column": "amount",
        "strategy": "mean",
        "value": None,
    }
    assert {c["name"]: c["dtype"] for c in v2["columns"]}["active"] == "boolean"

    # version 1 is unchanged
    p1 = client.get(f"{D}/{did}/preview", params={"version": 1}, headers=ana.headers).json()
    assert p1["total_rows"] == 4 and p1["rows"][0]["name"] == " Ann "
    p2 = client.get(f"{D}/{did}/preview", headers=ana.headers).json()  # default = latest
    assert p2["version"] == 2
    by_id = {r["id"]: r for r in p2["rows"]}
    assert (
        by_id[1]["name"] == "Ann" and by_id[2]["amount"] == 8.75 and by_id[3]["name"] == "unknown"
    )
    assert by_id[1]["active"] is True


def test_cleaning_is_reproducible(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    clean(client, ana, did, CLEAN_OPS, base_version=1)
    clean(client, ana, did, CLEAN_OPS, base_version=1)
    vs = client.get(f"{D}/{did}", headers=ana.headers).json()["versions"]
    assert [v["version"] for v in vs] == [1, 2, 3]
    assert (
        vs[1]["checksum_sha256"] == vs[2]["checksum_sha256"]
        or vs[1]["row_count"] == vs[2]["row_count"]
    )
    a = client.get(f"{D}/{did}/preview", params={"version": 2}, headers=ana.headers).json()["rows"]
    b = client.get(f"{D}/{did}/preview", params={"version": 3}, headers=ana.headers).json()["rows"]
    assert a == b


def test_each_operation(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    job = clean(
        client,
        ana,
        did,
        [
            {"op": "drop_missing", "columns": ["amount"]},
            {"op": "rename_column", "column": "amount", "new_name": "value"},
            {"op": "drop_columns", "columns": ["joined"]},
            {"op": "cast_type", "column": "id", "to": "string"},
        ],
    )
    assert job["status"] == "succeeded", job
    assert [s["rows_after"] for s in job["result"]["steps"]] == [2, 2, 2, 2]
    cols = {
        c["name"]: c["dtype"]
        for c in client.get(f"{D}/{did}", headers=ana.headers).json()["latest_version"]["columns"]
    }
    assert cols == {"id": "string", "name": "string", "value": "float", "active": "string"}


def test_failing_step_fails_job_and_creates_no_version(client, make_actor, db):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    job = clean(
        client, ana, did, [{"op": "drop_duplicates"}, {"op": "drop_columns", "columns": ["nope"]}]
    )
    assert job["status"] == "failed" and job["error_code"] == "unknown_column"
    assert job["error_message"].startswith("Step 2 (drop_columns)")
    assert db.scalar(select(DatasetVersion).where(DatasetVersion.version == 2)) is None
    assert client.get(f"{D}/{did}", headers=ana.headers).json()["status"] == "ready"


def test_cast_failure_does_not_leak_values(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    job = clean(client, ana, did, [{"op": "cast_type", "column": "active", "to": "integer"}])
    assert job["status"] == "failed" and job["error_code"] == "cast_failed"
    assert "yes" not in job["error_message"]


def test_invalid_operations_are_rejected_with_422(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)

    def post(body):
        return client.post(f"{D}/{did}/cleaning-jobs", json=body, headers=ana.headers).status_code

    assert post({"operations": []}) == 422
    assert post({"operations": [{"op": "run_python", "code": "x"}]}) == 422
    assert (
        post({"operations": [{"op": "fill_missing", "column": "a", "strategy": "constant"}]}) == 422
    )
    assert (
        post(
            {"operations": [{"op": "fill_missing", "column": "a", "strategy": "mean", "value": 1}]}
        )
        == 422
    )
    assert post({"operations": [{"op": "drop_duplicates", "evil": 1}]}) == 422
    assert post({"operations": [{"op": "drop_duplicates"}] * 51}) == 422
    assert post({"base_version": 0, "operations": [{"op": "drop_duplicates"}]}) == 422
    assert post({"base_version": 9, "operations": [{"op": "drop_duplicates"}]}) == 404


def test_removing_every_row_is_refused(client, make_actor, db):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana, content=b"a,b\n1,\n,2\n")  # every row has a gap
    job = clean(client, ana, did, [{"op": "drop_missing", "how": "any"}])
    assert job["status"] == "failed" and job["error_code"] == "empty_result"
    assert len(client.get(f"{D}/{did}", headers=ana.headers).json()["versions"]) == 1


# ---------- export ----------


def test_export_csv_and_json(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana, name="My Sales!")
    clean(client, ana, did, CLEAN_OPS)
    r = client.get(f"{D}/{did}/export", headers=ana.headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="My_Sales_v2.csv"'
    assert r.headers["x-content-type-options"] == "nosniff"
    lines = r.text.strip().splitlines()
    assert lines[0] == "id,name,amount,joined,active" and len(lines) == 4
    assert "unknown" in r.text and " Ann " not in r.text

    j = client.get(
        f"{D}/{did}/export", params={"format": "json", "version": 1}, headers=ana.headers
    )
    assert j.headers["content-type"] == "application/json" and len(j.json()) == 4
    assert (
        client.get(f"{D}/{did}/export", params={"format": "xml"}, headers=ana.headers).status_code
        == 422
    )


# ---------- jobs ----------


def test_jobs_listing_and_lookup(client, make_actor):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    clean(client, ana, did, [{"op": "drop_duplicates"}])
    jobs = client.get(f"{D}/{did}/jobs", headers=ana.headers).json()
    assert [j["job_type"] for j in jobs] == ["clean", "ingest"]
    assert client.get(f"{J}/not-a-uuid", headers=ana.headers).status_code == 422


def _queued_job(db, dataset_id, project_id, job_type="clean", params=None):
    from app.models.enums import JobStatus, JobType

    job = DataJob(
        project_id=uuid.UUID(str(project_id)),
        dataset_id=uuid.UUID(str(dataset_id)),
        job_type=JobType(job_type),
        status=JobStatus.queued,
        progress=0,
        params_json=params,
    )
    db.add(job)
    db.commit()
    return job


def test_queued_job_can_be_cancelled_and_then_never_runs(client, make_actor, db, engine):
    from app.core.config import get_settings
    from app.services.datasets.jobs import execute_job

    ana = make_actor("Ana")
    pid, did = ready_dataset(client, ana)
    job = _queued_job(
        db, did, pid, params={"base_version": 1, "operations": [{"op": "drop_duplicates"}]}
    )
    r = client.post(f"{J}/{job.id}/cancel", headers=ana.headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"

    execute_job(db, get_storage(), get_settings(), job.id)  # a worker picking it up late
    db.refresh(job)
    assert job.status.value == "cancelled"
    assert len(client.get(f"{D}/{did}", headers=ana.headers).json()["versions"]) == 1


def test_finished_job_cannot_be_cancelled(client, make_actor):
    ana = make_actor("Ana")
    pid, did = ready_dataset(client, ana)
    job_id = client.get(f"{D}/{did}/jobs", headers=ana.headers).json()[0]["id"]
    r = client.post(f"{J}/{job_id}/cancel", headers=ana.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "job_not_cancellable"


def test_running_a_job_twice_creates_only_one_version(client, make_actor, db):
    from app.core.config import get_settings
    from app.services.datasets.jobs import execute_job

    ana = make_actor("Ana")
    pid, did = ready_dataset(client, ana)
    job = _queued_job(
        db, did, pid, params={"base_version": 1, "operations": [{"op": "drop_duplicates"}]}
    )
    for _ in range(2):  # e.g. the broker redelivers the message
        execute_job(db, get_storage(), get_settings(), job.id)
    assert len(client.get(f"{D}/{did}", headers=ana.headers).json()["versions"]) == 2


def test_stale_running_jobs_are_failed(client, make_actor, db):
    from datetime import UTC, datetime, timedelta

    from app.models.enums import JobStatus
    from app.services.datasets.jobs import fail_stale_jobs

    ana = make_actor("Ana")
    pid, did = ready_dataset(client, ana)
    job = _queued_job(db, did, pid)
    job.status = JobStatus.running
    job.started_at = datetime.now(UTC) - timedelta(hours=3)
    db.commit()
    assert fail_stale_jobs(db, max_age_seconds=600) == 1
    db.refresh(job)
    assert job.status is JobStatus.failed and job.error_code == "worker_lost"


def test_queue_outage_fails_the_job_visibly(client, make_actor, app, db):
    from app.api.deps import get_enqueue

    def broken():
        def enqueue(_job_id):
            raise ConnectionError("redis down")

        return enqueue

    app.dependency_overrides[get_enqueue] = broken
    ana = make_actor("Ana")
    r = upload(client, ana, make_project(client, ana))
    assert r.status_code == 503 and r.json()["error"]["code"] == "job_queue_unavailable"
    job = db.scalar(select(DataJob))
    assert job.status.value == "failed" and job.error_code == "enqueue_failed"
    assert db.scalar(select(Dataset)).status.value == "failed"


def test_celery_task_runs_a_job(client, make_actor, db):
    from app.workers.tasks import run_job

    ana = make_actor("Ana")
    pid, did = ready_dataset(client, ana)
    job = _queued_job(db, did, pid, params={"version": 1}, job_type="profile")
    run_job.apply(args=[str(job.id)]).get()  # executes eagerly in this process
    db.refresh(job)
    assert job.status.value == "succeeded"


# ---------- deletion ----------


def test_delete_dataset_removes_rows_and_files(client, make_actor, db):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    clean(client, ana, did, [{"op": "drop_duplicates"}])
    storage = get_storage()
    keys = [db.scalar(select(Dataset.original_storage_key))] + [
        v.storage_key for v in db.scalars(select(DatasetVersion))
    ]
    assert len(keys) == 3 and all(storage.exists(k) for k in keys)

    assert client.delete(f"{D}/{did}", headers=ana.headers).status_code == 204
    assert client.get(f"{D}/{did}", headers=ana.headers).status_code == 404
    assert not any(storage.exists(k) for k in keys)
    db.expire_all()
    assert db.scalar(select(DatasetVersion)) is None and db.scalar(select(DataJob)) is None


def test_deleting_a_project_removes_its_dataset_files(client, make_actor, db):
    ana = make_actor("Ana")
    pid, did = ready_dataset(client, ana)
    keys = [
        db.scalar(select(Dataset.original_storage_key)),
        db.scalar(select(DatasetVersion.storage_key)),
    ]
    assert client.delete(f"{P}/{pid}", headers=ana.headers).status_code == 204
    storage = get_storage()
    assert not any(storage.exists(k) for k in keys)
    db.expire_all()
    assert db.scalar(select(Dataset)) is None


def test_events_are_audited(client, make_actor, db):
    ana = make_actor("Ana")
    _, did = ready_dataset(client, ana)
    clean(client, ana, did, [{"op": "drop_duplicates"}])
    client.get(f"{D}/{did}/export", headers=ana.headers)
    client.delete(f"{D}/{did}", headers=ana.headers)
    actions = {a for (a,) in db.execute(select(AuditLog.action)).all()}
    assert {
        "dataset.upload",
        "dataset.clean_requested",
        "dataset.export",
        "dataset.delete",
    } <= actions
