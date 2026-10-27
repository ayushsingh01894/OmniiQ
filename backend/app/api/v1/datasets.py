import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status

from app.api.deps import (
    CurrentUser,
    DbSession,
    EnqueueDep,
    LimiterDep,
    SettingsDep,
    StorageDep,
)
from app.core.errors import AppError
from app.schemas.cleaning import CleaningRequest
from app.schemas.dataset import (
    DatasetDetail,
    DatasetPage,
    JobOut,
    PreviewOut,
    ProfileRequest,
    UploadAccepted,
)
from app.services.datasets import service

router = APIRouter(tags=["datasets"])

VersionQuery = Annotated[int | None, Query(ge=1)]


def _throttle(limiter: LimiterDep, settings: SettingsDep, user: CurrentUser) -> None:
    """Expensive operations are limited per user (in-memory; see docs/security.md)."""
    limiter.hit(
        f"jobs:{user.id}", settings.job_rate_limit_attempts, settings.job_rate_limit_window_seconds
    )


Throttle = Annotated[None, Depends(_throttle)]


def _reject_oversized_request(request: Request, settings: SettingsDep) -> None:
    """Runs before the body is parsed, so an honest oversized upload is refused immediately."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_upload_bytes + 64 * 1024:
        raise AppError(413, "file_too_large", "The file is larger than the upload limit.")


@router.post(
    "/projects/{project_id}/datasets",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_dataset(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    storage: StorageDep,
    enqueue: EnqueueDep,
    _size: Annotated[None, Depends(_reject_oversized_request)],
    _throttle: Throttle,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form(max_length=120)] = None,
) -> UploadAccepted:
    dataset, job = service.create_dataset_upload(
        db,
        user,
        project_id,
        stream=file.file,
        filename=file.filename or "upload",
        name=name,
        storage=storage,
        settings=settings,
        enqueue=enqueue,
    )
    return UploadAccepted(dataset=dataset, job=job)


@router.get("/projects/{project_id}/datasets", response_model=DatasetPage)
def list_datasets(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DatasetPage:
    return service.list_datasets(db, user, project_id, limit=limit, offset=offset)


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DatasetDetail:
    return service.get_dataset_detail(db, user, dataset_id)


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: uuid.UUID, user: CurrentUser, db: DbSession, storage: StorageDep
) -> Response:
    service.delete_dataset(db, user, storage, dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/datasets/{dataset_id}/preview", response_model=PreviewOut)
def preview_dataset(
    dataset_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    version: VersionQuery = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PreviewOut:
    return service.preview(
        db, user, storage, dataset_id, version=version, limit=limit, offset=offset
    )


@router.get("/datasets/{dataset_id}/profile")
def get_profile(
    dataset_id: uuid.UUID, user: CurrentUser, db: DbSession, version: VersionQuery = None
) -> dict[str, object]:
    return service.get_profile(db, user, dataset_id, version)


@router.post(
    "/datasets/{dataset_id}/profile",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_profile(
    dataset_id: uuid.UUID,
    body: ProfileRequest,
    user: CurrentUser,
    db: DbSession,
    enqueue: EnqueueDep,
    _throttle: Throttle,
) -> JobOut:
    return service.request_profile(db, user, dataset_id, body.version, enqueue)


@router.post(
    "/datasets/{dataset_id}/cleaning-jobs",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_cleaning(
    dataset_id: uuid.UUID,
    body: CleaningRequest,
    user: CurrentUser,
    db: DbSession,
    enqueue: EnqueueDep,
    _throttle: Throttle,
) -> JobOut:
    return service.request_cleaning(db, user, dataset_id, body, enqueue)


@router.get("/datasets/{dataset_id}/jobs", response_model=list[JobOut])
def list_jobs(
    dataset_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[JobOut]:
    return service.list_jobs(db, user, dataset_id, limit)


@router.get("/datasets/{dataset_id}/export")
def export_dataset(
    dataset_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    version: VersionQuery = None,
    format: Literal["csv", "json"] = "csv",  # noqa: A002 (query parameter name)
) -> Response:
    body, media_type, filename = service.export(
        db, user, storage, dataset_id, version=version, fmt=format
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobOut:
    return service.get_job(db, user, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobOut:
    return service.cancel_job(db, user, job_id)
