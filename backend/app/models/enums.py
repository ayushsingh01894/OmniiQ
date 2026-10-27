from enum import StrEnum


class Role(StrEnum):
    viewer = "viewer"
    member = "member"
    admin = "admin"
    owner = "owner"


# Higher number = more privileges.
ROLE_RANK: dict[Role, int] = {Role.viewer: 0, Role.member: 1, Role.admin: 2, Role.owner: 3}


class DatasetFormat(StrEnum):
    csv = "csv"
    xlsx = "xlsx"


class DatasetStatus(StrEnum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class JobType(StrEnum):
    ingest = "ingest"
    profile = "profile"
    clean = "clean"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


TERMINAL_JOB_STATUSES = frozenset({JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled})
