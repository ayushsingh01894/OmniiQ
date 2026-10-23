import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DatasetFormat, DatasetStatus, JobStatus, JobType


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    nullable: bool


class VersionOut(BaseModel):
    id: uuid.UUID
    version: int
    parent_version: int | None
    row_count: int
    column_count: int
    size_bytes: int
    checksum_sha256: str
    columns: list[ColumnSchema]
    operations: list[dict[str, Any]] | None
    created_at: datetime


class DatasetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    original_filename: str
    format: DatasetFormat
    status: DatasetStatus
    original_size_bytes: int
    created_at: datetime
    latest_version: VersionOut | None


class DatasetDetail(DatasetOut):
    versions: list[VersionOut]


class DatasetPage(BaseModel):
    items: list[DatasetOut]
    total: int
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class JobOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    job_type: JobType
    status: JobStatus
    progress: int
    error_code: str | None
    error_message: str | None
    result: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class UploadAccepted(BaseModel):
    dataset: DatasetOut
    job: JobOut


class PreviewOut(BaseModel):
    version: int
    columns: list[ColumnSchema]
    rows: list[dict[str, Any]]
    total_rows: int
    limit: int
    offset: int


class ProfileRequest(BaseModel):
    version: int | None = Field(default=None, ge=1)
