import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DatasetFormat, DatasetStatus, JobStatus, JobType


def _now() -> datetime:
    # Microsecond precision: lists sort by creation time, and SQLite's now() only has seconds.
    return datetime.now(UTC)


def _enum[E: StrEnum](cls: type[E], name: str, length: int) -> Enum:
    return Enum(
        cls,
        name=name,
        native_enum=False,
        length=length,
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_datasets_project_id_name"),
        Index("ix_datasets_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    # Display only. Never used to build paths: storage keys are generated from ids.
    original_filename: Mapped[str] = mapped_column(String(255))
    format: Mapped[DatasetFormat] = mapped_column(_enum(DatasetFormat, "dataset_format", 8))
    status: Mapped[DatasetStatus] = mapped_column(_enum(DatasetStatus, "dataset_status", 16))
    # The untouched upload. Versions are derived from it and never modify it.
    original_storage_key: Mapped[str] = mapped_column(String(255))
    original_size_bytes: Mapped[int] = mapped_column(BigInteger)
    original_checksum_sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_dataset_id_version"),
        Index("ix_dataset_versions_dataset_id", "dataset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(String(255))  # normalized Parquet file
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    schema_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    # The cleaning operations that produced this version from its parent (null for version 1).
    operations_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataJob(Base):
    __tablename__ = "data_jobs"
    __table_args__ = (
        Index("ix_data_jobs_dataset_id_created_at", "dataset_id", "created_at"),
        Index("ix_data_jobs_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # project_id is denormalized so authorization never needs to touch the dataset.
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    job_type: Mapped[JobType] = mapped_column(_enum(JobType, "job_type", 16))
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus, "job_status", 16))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    params_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))  # always sanitized
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
