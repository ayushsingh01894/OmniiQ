import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    action: str,
    resource_type: str,
    actor_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Adds an audit row to the caller's transaction (it commits together with the change)."""
    db.add(
        AuditLog(
            action=action,
            resource_type=resource_type,
            actor_id=actor_id,
            organization_id=organization_id,
            resource_id=str(resource_id) if resource_id is not None else None,
            details=details,
        )
    )
