"""Authorization. Every organization- or project-scoped operation goes through here."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, forbidden, not_found
from app.models import ROLE_RANK, DataJob, Dataset, OrganizationMember, Project, Role, User


def _membership(db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> OrganizationMember | None:
    return db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id, OrganizationMember.organization_id == org_id
        )
    )


def require_org_role(
    db: Session, user: User, org_id: uuid.UUID, minimum: Role
) -> OrganizationMember:
    """Non-members get 404 (not 403) so organization ids cannot be probed for existence."""
    membership = _membership(db, user.id, org_id)
    if membership is None:
        raise not_found("organization_not_found", "Organization not found.")
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise forbidden()
    return membership


def get_project_for_user(
    db: Session, user: User, project_id: uuid.UUID, minimum: Role
) -> tuple[Project, OrganizationMember]:
    """Missing project and project-in-someone-else's-org are indistinguishable (both 404)."""
    project = db.get(Project, project_id)
    membership = _membership(db, user.id, project.organization_id) if project else None
    if project is None or membership is None:
        raise not_found("project_not_found", "Project not found.")
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise forbidden()
    return project, membership


def can_grant_role(granter: Role, granted: Role) -> bool:
    """Owners may grant any role; admins may grant member and viewer only."""
    if granter == Role.owner:
        return True
    return granter == Role.admin and granted in (Role.member, Role.viewer)


def ensure_can_grant(granter: Role, granted: Role) -> None:
    if not can_grant_role(granter, granted):
        raise AppError(403, "forbidden", f"Your role cannot grant the '{granted.value}' role.")


def get_dataset_for_user(db: Session, user: User, dataset_id: uuid.UUID, minimum: Role) -> Dataset:
    """Access to a dataset is access to its project's organization. Foreign = missing (404)."""
    dataset = db.get(Dataset, dataset_id)
    project = db.get(Project, dataset.project_id) if dataset else None
    membership = _membership(db, user.id, project.organization_id) if project else None
    if dataset is None or membership is None:
        raise not_found("dataset_not_found", "Dataset not found.")
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise forbidden()
    return dataset


def get_job_for_user(db: Session, user: User, job_id: uuid.UUID, minimum: Role) -> DataJob:
    job = db.get(DataJob, job_id)
    project = db.get(Project, job.project_id) if job else None
    membership = _membership(db, user.id, project.organization_id) if project else None
    if job is None or membership is None:
        raise not_found("job_not_found", "Job not found.")
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise forbidden()
    return job
