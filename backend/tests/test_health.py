from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


def _client(app) -> TestClient:
    return TestClient(app)


def test_live_returns_ok(app):
    res = _client(app).get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ready_returns_ready_when_database_answers(app):
    engine = create_engine("sqlite://", poolclass=StaticPool)

    def override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override
    res = _client(app).get("/api/v1/health/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready", "database": "up"}


def test_ready_returns_503_without_leaking_details_when_database_down(app):
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("password=hunter2 host=db.internal")

    def override() -> Iterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = override
    res = _client(app).get("/api/v1/health/ready")
    assert res.status_code == 503
    assert res.json() == {"status": "not_ready", "database": "down"}
    assert "hunter2" not in res.text


def test_openapi_is_served_under_versioned_prefix(app):
    res = _client(app).get("/api/v1/openapi.json")
    assert res.status_code == 200
    assert "/api/v1/health/live" in res.json()["paths"]
