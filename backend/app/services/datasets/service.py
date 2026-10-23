"""Dataset use-cases. Every function authorizes first (services/access.py), then acts."""

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, conflict, not_found
from app.models import DataJob, Dataset, DatasetVersion, Project, Role, User
from app.models.enums import DatasetStatus, JobStatus, JobType
from app.schemas.cleaning import CleaningRequest
from app.schemas.dataset import (
    ColumnSchema,
    DatasetDetail,
    DatasetOut,
    DatasetPage,
    JobOut,
    PreviewOut,
    VersionOut,
)
from app.services import access, audit
from app.services.datasets import ingest
from app.services.datasets.errors import DatasetError
from app.services.datasets.frames import read_version_frame, to_json_records
from app.storage.base import Storage
from app.workers.dispatch import Enqueue

logger = logging.getLogger(__name__)

_STATUS_FOR_CODE = {"unsupported_file_type": 415, "file_too_large": 413}


# ---------- output mapping ----------


def _version_out(v: DatasetVersion, parent_number: int | None) -> VersionOut:
    return VersionOut(
        id=v.id,
        version=v.version,
        parent_version=parent_number,
        row_count=v.row_count,
        column_count=v.column_count,
        size_bytes=v.size_bytes,
        checksum_sha256=v.checksum_sha256,
        columns=[ColumnSchema(**c) for c in v.schema_json],
        operations=v.operations_json,
        created_at=v.created_at,
    )


def _versions_out(versions: list[DatasetVersion]) -> list[VersionOut]:
    number_by_id = {v.id: v.version for v in versions}
    return [
        _version_out(v, number_by_id.get(v.parent_version_id) if v.parent_version_id else None)
        for v in versions
    ]


def _dataset_out(d: Dataset, versions: list[DatasetVersion]) -> DatasetOut:
    outs = _versions_out(versions)
    return DatasetOut(
        id=d.id,
        project_id=d.project_id,
        name=d.name,
        original_filename=d.original_filename,
        format=d.format,
        status=d.status,
        original_size_bytes=d.original_size_bytes,
        created_at=d.created_at,
        latest_version=outs[-1] if outs else None,
    )


def job_out(j: DataJob) -> JobOut:
    return JobOut(
        id=j.id,
        dataset_id=j.dataset_id,
        job_type=j.job_type,
        status=j.status,
        progress=j.progress,
        error_code=j.error_code,
        error_message=j.error_message,
        result=j.result_json,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
    )


def _versions_of(
    db: Session, dataset_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[DatasetVersion]]:
    grouped: dict[uuid.UUID, list[DatasetVersion]] = {i: [] for i in dataset_ids}
    if dataset_ids:
        rows = db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id.in_(dataset_ids))
            .order_by(DatasetVersion.dataset_id, DatasetVersion.version)
        )
        for v in rows:
            grouped[v.dataset_id].append(v)
    return grouped


# ---------- job plumbing ----------


def _enqueue(db: Session, job: DataJob, enqueue: Enqueue) -> None:
    """Called after the job row is committed. If the queue is down, the job fails visibly."""
    try:
        enqueue(job.id)
    except Exception:
        logger.exception("could not enqueue job %s", job.id)
        from app.services.datasets.jobs import mark_failed

        mark_failed(db, job.id, "enqueue_failed", "The job queue is unavailable.")
        raise AppError(
            503, "job_queue_unavailable", "Background processing is unavailable. Try again shortly."
        ) from None


def _new_job(
    db: Session, user: User, dataset: Dataset, job_type: JobType, params: dict[str, Any] | None
) -> DataJob:
    job = DataJob(
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        job_type=job_type,
        status=JobStatus.queued,
        progress=0,
        params_json=params,
        created_by=user.id,
    )
    db.add(job)
    return job


# ---------- upload ----------


class _LimitedHashingReader:
    """Wraps the upload stream: enforces the size limit and computes the checksum while copying."""

    def __init__(self, stream: BinaryIO, max_bytes: int) -> None:
        self._stream = stream
        self._max = max_bytes
        self.total = 0
        self.digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        self.total += len(chunk)
        if self.total > self._max:
            raise AppError(413, "file_too_large", "The file is larger than the upload limit.")
        self.digest.update(chunk)
        return chunk


def create_dataset_upload(
    db: Session,
    user: User,
    project_id: uuid.UUID,
    *,
    stream: BinaryIO,
    filename: str,
    name: str | None,
    storage: Storage,
    settings: Settings,
    enqueue: Enqueue,
) -> tuple[DatasetOut, JobOut]:
    project, _ = access.get_project_for_user(db, user, project_id, Role.member)

    display_name = (name or "").strip() or re.sub(
        r"\.[^.]*$", "", filename.rsplit("/", 1)[-1]
    ).strip()
    display_name = display_name[:120]
    if not display_name:
        raise AppError(422, "validation_error", "A dataset name is required.")
    if db.scalar(
        select(Dataset.id).where(Dataset.project_id == project.id, Dataset.name == display_name)
    ):
        raise conflict("dataset_name_taken", "A dataset with this name already exists.")

    try:
        fmt = ingest.detect_format(filename)
        head = ingest.head_of(stream)
        if not head:
            raise DatasetError("empty_dataset", "The file is empty.")
        ingest.check_content_signature(head, fmt)
        if fmt.value == "xlsx":
            ingest.check_xlsx_zip(stream, settings)
            stream.seek(0)
    except DatasetError as exc:
        raise AppError(_STATUS_FOR_CODE.get(exc.code, 422), exc.code, exc.message) from None

    dataset_id = uuid.uuid4()
    key = f"datasets/{dataset_id}/original.{fmt.value}"
    reader = _LimitedHashingReader(stream, settings.max_upload_bytes)
    storage.save(key, reader)  # type: ignore[arg-type]  # only .read() is used

    dataset = Dataset(
        id=dataset_id,
        project_id=project.id,
        name=display_name,
        original_filename=filename.rsplit("/", 1)[-1][:255],
        format=fmt,
        status=DatasetStatus.processing,
        original_storage_key=key,
        original_size_bytes=reader.total,
        original_checksum_sha256=reader.digest.hexdigest(),
        created_by=user.id,
    )
    db.add(dataset)
    try:
        db.flush()
        job = _new_job(db, user, dataset, JobType.ingest, None)
        audit.record(
            db,
            action="dataset.upload",
            resource_type="dataset",
            actor_id=user.id,
            organization_id=project.organization_id,
            resource_id=dataset.id,
            details={"size_bytes": reader.total, "format": fmt.value},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(key)
        raise conflict("dataset_name_taken", "A dataset with this name already exists.") from None
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    db.refresh(dataset)
    db.refresh(job)
    result = (_dataset_out(dataset, []), job_out(job))
    _enqueue(db, job, enqueue)
    return result


# ---------- reads ----------


def list_datasets(
    db: Session, user: User, project_id: uuid.UUID, *, limit: int, offset: int
) -> DatasetPage:
    access.get_project_for_user(db, user, project_id, Role.viewer)
    total = (
        db.scalar(select(func.count()).select_from(Dataset).where(Dataset.project_id == project_id))
        or 0
    )
    datasets = list(
        db.scalars(
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.desc(), Dataset.id)
            .limit(limit)
            .offset(offset)
        )
    )
    versions = _versions_of(db, [d.id for d in datasets])
    return DatasetPage(
        items=[_dataset_out(d, versions[d.id]) for d in datasets],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_dataset_detail(db: Session, user: User, dataset_id: uuid.UUID) -> DatasetDetail:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.viewer)
    versions = _versions_of(db, [dataset.id])[dataset.id]
    base = _dataset_out(dataset, versions)
    return DatasetDetail(**base.model_dump(), versions=_versions_out(versions))


def _resolve_version(db: Session, dataset: Dataset, number: int | None) -> DatasetVersion:
    if dataset.status is not DatasetStatus.ready:
        raise conflict("dataset_not_ready", "This dataset has no usable data yet.")
    query = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
    if number is None:
        query = query.order_by(DatasetVersion.version.desc()).limit(1)
    else:
        query = query.where(DatasetVersion.version == number)
    version = db.scalar(query)
    if version is None:
        raise not_found("version_not_found", "That version does not exist.")
    return version


def preview(
    db: Session,
    user: User,
    storage: Storage,
    dataset_id: uuid.UUID,
    *,
    version: int | None,
    limit: int,
    offset: int,
) -> PreviewOut:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.viewer)
    v = _resolve_version(db, dataset, version)
    df = read_version_frame(storage, v.storage_key)
    return PreviewOut(
        version=v.version,
        columns=[ColumnSchema(**c) for c in v.schema_json],
        rows=to_json_records(df.iloc[offset : offset + limit]),
        total_rows=int(len(df)),
        limit=limit,
        offset=offset,
    )


def get_profile(
    db: Session, user: User, dataset_id: uuid.UUID, version: int | None
) -> dict[str, Any]:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.viewer)
    v = _resolve_version(db, dataset, version)
    if v.profile_json is None:
        raise not_found("profile_not_ready", "No profile has been computed for this version yet.")
    return {"version": v.version, **v.profile_json}


def export(
    db: Session,
    user: User,
    storage: Storage,
    dataset_id: uuid.UUID,
    *,
    version: int | None,
    fmt: str,
) -> tuple[bytes, str, str]:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.viewer)
    v = _resolve_version(db, dataset, version)
    df = read_version_frame(storage, v.storage_key)
    audit.record(
        db,
        action="dataset.export",
        resource_type="dataset",
        actor_id=user.id,
        organization_id=db.get(Project, dataset.project_id).organization_id,  # type: ignore[union-attr]
        resource_id=dataset.id,
        details={"version": v.version, "format": fmt},
    )
    db.commit()
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", dataset.name).strip("_") or "dataset"
    if fmt == "json":
        return (
            str(df.to_json(orient="records", date_format="iso")).encode(),
            "application/json",
            f"{safe}_v{v.version}.json",
        )
    return (
        str(df.to_csv(index=False)).encode(),
        "text/csv; charset=utf-8",
        f"{safe}_v{v.version}.csv",
    )


# ---------- jobs ----------


def request_profile(
    db: Session, user: User, dataset_id: uuid.UUID, version: int | None, enqueue: Enqueue
) -> JobOut:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.member)
    v = _resolve_version(db, dataset, version)
    job = _new_job(db, user, dataset, JobType.profile, {"version": v.version})
    db.commit()
    db.refresh(job)
    out = job_out(job)
    _enqueue(db, job, enqueue)
    return out


def request_cleaning(
    db: Session, user: User, dataset_id: uuid.UUID, body: CleaningRequest, enqueue: Enqueue
) -> JobOut:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.member)
    base = _resolve_version(db, dataset, body.base_version)
    params = {
        "base_version": base.version,
        "operations": [op.model_dump(mode="json") for op in body.operations],
    }
    job = _new_job(db, user, dataset, JobType.clean, params)
    audit.record(
        db,
        action="dataset.clean_requested",
        resource_type="dataset",
        actor_id=user.id,
        organization_id=db.get(Project, dataset.project_id).organization_id,  # type: ignore[union-attr]
        resource_id=dataset.id,
        details={"base_version": base.version, "operation_count": len(body.operations)},
    )
    db.commit()
    db.refresh(job)
    out = job_out(job)
    _enqueue(db, job, enqueue)
    return out


def list_jobs(db: Session, user: User, dataset_id: uuid.UUID, limit: int) -> list[JobOut]:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.viewer)
    jobs = db.scalars(
        select(DataJob)
        .where(DataJob.dataset_id == dataset.id)
        .order_by(DataJob.created_at.desc(), DataJob.id)
        .limit(limit)
    )
    return [job_out(j) for j in jobs]


def get_job(db: Session, user: User, job_id: uuid.UUID) -> JobOut:
    return job_out(access.get_job_for_user(db, user, job_id, Role.viewer))


def cancel_job(db: Session, user: User, job_id: uuid.UUID) -> JobOut:
    job = access.get_job_for_user(db, user, job_id, Role.member)
    # Conditional update: only a still-queued job can be cancelled (a worker may claim it first).
    result = db.execute(
        update(DataJob)
        .where(DataJob.id == job.id, DataJob.status == JobStatus.queued)
        .values(status=JobStatus.cancelled, finished_at=datetime.now(UTC))
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        db.rollback()
        raise conflict("job_not_cancellable", "Only a queued job can be cancelled.")
    if job.job_type is JobType.ingest:
        db.execute(
            update(Dataset).where(Dataset.id == job.dataset_id).values(status=DatasetStatus.failed)
        )
    db.commit()
    db.refresh(job)
    return job_out(job)


# ---------- delete ----------


def storage_keys_for_datasets(db: Session, dataset_ids: list[uuid.UUID]) -> list[str]:
    if not dataset_ids:
        return []
    originals = db.scalars(select(Dataset.original_storage_key).where(Dataset.id.in_(dataset_ids)))
    versions = db.scalars(
        select(DatasetVersion.storage_key).where(DatasetVersion.dataset_id.in_(dataset_ids))
    )
    return [*originals, *versions]


def purge_storage(storage: Storage, keys: list[str]) -> None:
    """After the DB commit. A failure leaves an orphan file, never a dangling database row."""
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            logger.exception("could not delete stored file %s", key)


def delete_dataset(db: Session, user: User, storage: Storage, dataset_id: uuid.UUID) -> None:
    dataset = access.get_dataset_for_user(db, user, dataset_id, Role.admin)
    keys = storage_keys_for_datasets(db, [dataset.id])
    audit.record(
        db,
        action="dataset.delete",
        resource_type="dataset",
        actor_id=user.id,
        organization_id=db.get(Project, dataset.project_id).organization_id,  # type: ignore[union-attr]
        resource_id=dataset.id,
        details={"name": dataset.name},
    )
    db.delete(dataset)
    db.commit()
    purge_storage(storage, keys)
