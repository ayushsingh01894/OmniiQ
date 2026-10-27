import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["up", "down"]


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    """Process is running. Does not touch dependencies."""
    return LiveResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
def ready(response: Response, db: Annotated[Session, Depends(get_db)]) -> ReadyResponse:
    """Process can serve traffic: the database answers a trivial query."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        # Log details server-side; never leak connection strings to the caller.
        logger.exception("readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="not_ready", database="down")
    return ReadyResponse(status="ready", database="up")
