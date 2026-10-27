import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession, StorageDep
from app.schemas.project import ProjectCreate, ProjectOut, ProjectPage, ProjectUpdate
from app.services import projects as project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectPage)
def list_projects(
    user: CurrentUser,
    db: DbSession,
    organization_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectPage:
    return project_service.list_projects(
        db, user, organization_id=organization_id, limit=limit, offset=offset
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, user: CurrentUser, db: DbSession) -> ProjectOut:
    return ProjectOut.model_validate(project_service.create_project(db, user, body))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ProjectOut:
    return ProjectOut.model_validate(project_service.get_project(db, user, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, user: CurrentUser, db: DbSession
) -> ProjectOut:
    return ProjectOut.model_validate(project_service.update_project(db, user, project_id, body))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession, storage: StorageDep
) -> Response:
    project_service.delete_project(db, user, storage, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
