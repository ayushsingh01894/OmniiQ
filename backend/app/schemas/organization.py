import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import Role
from app.schemas.common import Name


class OrganizationCreate(BaseModel):
    name: Name


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: Role  # the caller's role in this organization
    created_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
