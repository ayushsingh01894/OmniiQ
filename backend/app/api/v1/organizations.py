import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.organization import MemberAdd, MemberOut, OrganizationCreate, OrganizationOut
from app.services import organizations as org_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationOut])
def list_organizations(user: CurrentUser, db: DbSession) -> list[OrganizationOut]:
    return org_service.list_organizations(db, user)


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrganizationCreate, user: CurrentUser, db: DbSession
) -> OrganizationOut:
    return org_service.create_organization(db, user, body.name)


@router.get("/{organization_id}/members", response_model=list[MemberOut])
def list_members(organization_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[MemberOut]:
    return org_service.list_members(db, user, organization_id)


@router.post(
    "/{organization_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
def add_member(
    organization_id: uuid.UUID, body: MemberAdd, user: CurrentUser, db: DbSession
) -> MemberOut:
    return org_service.add_member(db, user, organization_id, email=body.email, role=body.role)
