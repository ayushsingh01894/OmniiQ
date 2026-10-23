import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Name

Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class ProjectCreate(BaseModel):
    organization_id: uuid.UUID
    name: Name
    description: Description | None = None


class ProjectUpdate(BaseModel):
    name: Name | None = None
    description: Description | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectOut]
    total: int
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
