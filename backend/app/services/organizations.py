import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.models import Organization, OrganizationMember, Role, User
from app.schemas.organization import MemberOut, OrganizationOut
from app.services import access, audit
from app.utils.slug import unique_slug


def _org_out(org: Organization, role: Role) -> OrganizationOut:
    return OrganizationOut(
        id=org.id, name=org.name, slug=org.slug, role=role, created_at=org.created_at
    )


def create_organization(db: Session, user: User, name: str) -> OrganizationOut:
    org = Organization(name=name, slug=unique_slug(name))
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=Role.owner))
    audit.record(
        db,
        action="organization.create",
        resource_type="organization",
        actor_id=user.id,
        organization_id=org.id,
        resource_id=org.id,
    )
    db.commit()
    db.refresh(org)
    return _org_out(org, Role.owner)


def list_organizations(db: Session, user: User) -> list[OrganizationOut]:
    rows = db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at, Organization.name)
    ).all()
    return [_org_out(org, role) for org, role in rows]


def list_members(db: Session, user: User, org_id: uuid.UUID) -> list[MemberOut]:
    access.require_org_role(db, user, org_id, Role.viewer)
    rows = db.execute(
        select(User, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(User.email)
    ).all()
    return [
        MemberOut(user_id=u.id, email=u.email, display_name=u.display_name, role=r) for u, r in rows
    ]


def add_member(db: Session, user: User, org_id: uuid.UUID, *, email: str, role: Role) -> MemberOut:
    acting = access.require_org_role(db, user, org_id, Role.admin)
    access.ensure_can_grant(acting.role, role)

    target = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if target is None:
        raise not_found("user_not_found", "No registered user has that email.")
    db.add(OrganizationMember(organization_id=org_id, user_id=target.id, role=role))
    audit.record(
        db,
        action="organization.member_add",
        resource_type="organization",
        actor_id=user.id,
        organization_id=org_id,
        resource_id=org_id,
        details={"user_id": str(target.id), "role": role.value},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("already_a_member", "That user is already a member.") from None
    return MemberOut(
        user_id=target.id, email=target.email, display_name=target.display_name, role=role
    )
