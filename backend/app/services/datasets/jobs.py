"""Background job execution. Runs in a worker (Celery) or after the response (inline mode).

Rules this module enforces:
  * a job runs at most once: it is *claimed* with a conditional UPDATE (queued -> running);
  * every outcome ends in a terminal state with progress and sanitized error info;
  * unexpected exceptions are logged server-side and shown to users as a generic message;
  * a file written by a job that then fails to commit is deleted again.
"""

import io
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pydantic import TypeAdapter
from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import DataJob, Dataset, DatasetVersion
from app.models.enums import DatasetStatus, JobStatus, JobType
from app.schemas.cleaning import Operation
from app.services.datasets.cleaning import apply_operations
from app.services.datasets.errors import DatasetError
from app.services.datasets.frames import (
    frame_to_parquet,
    infer_schema,
    read_version_frame,
    sha256_hex,
)
from app.services.datasets.ingest import read_original
from app.services.datasets.profiling import build_profile
from app.storage.base import Storage

logger = logging.getLogger(__name__)
_OPERATIONS = TypeAdapter(list[Operation])


def _claim(db: Session, job_id: uuid.UUID) -> bool:
    result = cast(
        "CursorResult[Any]",
        db.execute(
            update(DataJob)
            .where(DataJob.id == job_id, DataJob.status == JobStatus.queued)
            .values(status=JobStatus.running, started_at=func.now(), progress=5)
        ),
    )
    db.commit()
    return result.rowcount == 1


def _progress(db: Session, job_id: uuid.UUID, percent: int) -> None:
    db.execute(update(DataJob).where(DataJob.id == job_id).values(progress=percent))
    db.commit()


def _finish_ok(db: Session, job: DataJob, result: dict[str, Any]) -> None:
    job.status = JobStatus.succeeded
    job.progress = 100
    job.result_json = result
    job.finished_at = datetime.now(UTC)


def mark_failed(db: Session, job_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    job = db.get(DataJob, job_id)
    if job is None:
        return
    job.status = JobStatus.failed
    job.error_code = code
    job.error_message = message[:500]
    job.finished_at = datetime.now(UTC)
    if job.job_type is JobType.ingest:
        dataset = db.get(Dataset, job.dataset_id)
        if dataset is not None:
            dataset.status = DatasetStatus.failed
    db.commit()


def _new_version(
    db: Session,
    storage: Storage,
    dataset: Dataset,
    job: DataJob,
    df: Any,
    profile: dict[str, Any],
    *,
    number: int,
    parent_id: uuid.UUID | None,
    operations: list[dict[str, Any]] | None,
) -> tuple[DatasetVersion, str]:
    data = frame_to_parquet(df)
    version_id = uuid.uuid4()
    # The key includes the version's own id, so two racing jobs can never overwrite each other.
    key = f"datasets/{dataset.id}/versions/{version_id}.parquet"
    storage.save(key, io.BytesIO(data))
    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset.id,
        version=number,
        parent_version_id=parent_id,
        storage_key=key,
        checksum_sha256=sha256_hex(data),
        size_bytes=len(data),
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        schema_json=infer_schema(df),
        operations_json=operations,
        profile_json=profile,
        created_by=job.created_by,
    )
    db.add(version)
    return version, key


def _run_ingest(db: Session, storage: Storage, settings: Settings, job: DataJob) -> None:
    dataset = db.get(Dataset, job.dataset_id)
    if dataset is None:
        raise DatasetError("dataset_not_found", "The dataset no longer exists.")
    df = read_original(storage, dataset.original_storage_key, dataset.format, settings)
    _progress(db, job.id, 40)
    profile = build_profile(df)
    _progress(db, job.id, 70)
    version, key = _new_version(
        db, storage, dataset, job, df, profile, number=1, parent_id=None, operations=None
    )
    dataset.status = DatasetStatus.ready
    _finish_ok(db, job, {"version": 1, "rows": version.row_count, "columns": version.column_count})
    try:
        db.commit()
    except Exception:
        storage.delete(key)
        raise


def _version_by_number(db: Session, dataset_id: uuid.UUID, number: int) -> DatasetVersion:
    version = db.scalar(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id, DatasetVersion.version == number
        )
    )
    if version is None:
        raise DatasetError("version_not_found", f"Version {number} does not exist.")
    return version


def _run_profile(db: Session, storage: Storage, job: DataJob) -> None:
    number = int((job.params_json or {})["version"])
    version = _version_by_number(db, job.dataset_id, number)
    df = read_version_frame(storage, version.storage_key)
    _progress(db, job.id, 50)
    version.profile_json = build_profile(df)
    _finish_ok(db, job, {"version": number, "issues": len(version.profile_json["issues"])})
    db.commit()


def _run_clean(db: Session, storage: Storage, job: DataJob) -> None:
    params = job.params_json or {}
    base_number = int(params["base_version"])
    operations = _OPERATIONS.validate_python(params["operations"])
    dataset = db.get(Dataset, job.dataset_id)
    if dataset is None:
        raise DatasetError("dataset_not_found", "The dataset no longer exists.")
    base = _version_by_number(db, job.dataset_id, base_number)
    df = read_version_frame(storage, base.storage_key)
    _progress(db, job.id, 30)
    cleaned, steps = apply_operations(df, operations)
    if len(cleaned) == 0:
        raise DatasetError("empty_result", "The cleaning steps removed every row.")
    _progress(db, job.id, 60)
    profile = build_profile(cleaned)
    next_number = (
        db.scalar(
            select(func.max(DatasetVersion.version)).where(DatasetVersion.dataset_id == dataset.id)
        )
        or 0
    ) + 1
    version, key = _new_version(
        db,
        storage,
        dataset,
        job,
        cleaned,
        profile,
        number=next_number,
        parent_id=base.id,
        operations=_OPERATIONS.dump_python(operations, mode="json"),
    )
    _finish_ok(
        db,
        job,
        {
            "version": next_number,
            "base_version": base_number,
            "rows_before": int(len(df)),
            "rows_after": version.row_count,
            "steps": steps,
        },
    )
    try:
        db.commit()
    except IntegrityError:
        storage.delete(key)
        raise DatasetError(
            "version_conflict", "Another change created a new version first. Run the job again."
        ) from None
    except Exception:
        storage.delete(key)
        raise


def execute_job(db: Session, storage: Storage, settings: Settings, job_id: uuid.UUID) -> None:
    if not _claim(db, job_id):
        return  # already running, finished, or cancelled: running it twice would be wrong
    job = db.get(DataJob, job_id)
    if job is None:
        return
    try:
        if job.job_type is JobType.ingest:
            _run_ingest(db, storage, settings, job)
        elif job.job_type is JobType.profile:
            _run_profile(db, storage, job)
        else:
            _run_clean(db, storage, job)
    except DatasetError as exc:
        mark_failed(db, job_id, exc.code, exc.message)
    except Exception as exc:
        if type(exc).__name__ == "SoftTimeLimitExceeded":
            mark_failed(db, job_id, "timeout", "Processing took too long and was stopped.")
        else:
            logger.exception("job %s failed unexpectedly", job_id)  # details stay in server logs
            mark_failed(db, job_id, "internal_error", "Processing failed unexpectedly.")


def fail_stale_jobs(db: Session, max_age_seconds: int) -> int:
    """Jobs stuck in 'running' (e.g. the worker was killed) are marked failed so users can retry."""
    cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    stale = db.scalars(
        select(DataJob.id).where(DataJob.status == JobStatus.running, DataJob.started_at < cutoff)
    ).all()
    for job_id in stale:
        mark_failed(db, job_id, "worker_lost", "The worker stopped before finishing this job.")
    return len(stale)
