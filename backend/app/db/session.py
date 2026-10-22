from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping drops stale connections instead of failing the next request.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session_factory() -> sessionmaker[Session]:
    """Used by code that runs outside a request (background jobs)."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
