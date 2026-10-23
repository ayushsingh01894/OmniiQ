import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict
from app.models import Dataset, OrganizationMember, Project, Role, User
from app.schemas.project import ProjectCreate, ProjectPage, ProjectUpdate
from app.services import access, audit
from app.services.datasets import service as dataset_service
from app.storage.base import Storage

_NAME_TAKEN = ("project_name_taken", "A project with this name already exists in the organization.")


def create_project(db: Session, user: User, data: ProjectCreate) -> Project:
    access.require_org_role(db, user, data.organization_id, Role.member)
    project = Project(
        organization_id=data.organization_id,
        name=data.name,
        description=data.description,
        created_by=user.id,
    )
    db.add(project)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(*_NAME_TAKEN) from None
    audit.record(
        db,
        action="project.create",
        resource_type="project",
        actor_id=user.id,
        organization_id=project.organization_id,
        resource_id=project.id,
    )
    db.commit()
    db.refresh(project)
    return project


def list_projects(
    db: Session, user: User, *, organization_id: uuid.UUID | None, limit: int, offset: int
) -> ProjectPage:
    if organization_id is not None:
        access.require_org_role(db, user, organization_id, Role.viewer)

    # Only projects in organizations the caller belongs to can ever match.
    visible = select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == user.id
    )
    conditions: list[ColumnElement[bool]] = [Project.organization_id.in_(visible)]
    if organization_id is not None:
        conditions.append(Project.organization_id == organization_id)

    total = db.scalar(select(func.count()).select_from(Project).where(*conditions)) or 0
    items = db.scalars(
        select(Project)
        .where(*conditions)
        .order_by(Project.created_at.desc(), Project.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return ProjectPage.model_validate(
        {"items": items, "total": total, "limit": limit, "offset": offset}
    )


def get_project(db: Session, user: User, project_id: uuid.UUID) -> Project:
    project, _ = access.get_project_for_user(db, user, project_id, Role.viewer)
    return project


def update_project(db: Session, user: User, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
    project, _ = access.get_project_for_user(db, user, project_id, Role.member)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is None:
        changes.pop("name", None)  # name cannot be cleared
    for field, value in changes.items():
        setattr(project, field, value)
    audit.record(
        db,
        action="project.update",
        resource_type="project",
        actor_id=user.id,
        organization_id=project.organization_id,
        resource_id=project.id,
        details={"fields": sorted(changes)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict(*_NAME_TAKEN) from None
    db.refresh(project)
    return project


def delete_project(db: Session, user: User, storage: Storage, project_id: uuid.UUID) -> None:
    project, _ = access.get_project_for_user(db, user, project_id, Role.admin)
    dataset_ids = list(db.scalars(select(Dataset.id).where(Dataset.project_id == project.id)))
    keys = dataset_service.storage_keys_for_datasets(db, dataset_ids)
    audit.record(
        db,
        action="project.delete",
        resource_type="project",
        actor_id=user.id,
        organization_id=project.organization_id,
        resource_id=project.id,
        details={"name": project.name},
    )
    db.delete(project)
    db.commit()
    dataset_service.purge_storage(storage, keys)
