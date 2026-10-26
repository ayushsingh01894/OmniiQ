import os

# Must be set before app modules read settings. Tests never need a real Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-that-is-at-least-32-chars")
# One throw-away storage directory for the whole test run (keys are uuid-based, no collisions).
os.environ.setdefault("STORAGE_ROOT", __import__("tempfile").mkdtemp(prefix="omniiq-test-storage-"))

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402, F401
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

PASSWORD = "correct horse battery"


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """SQLite in memory by default. Set TEST_DATABASE_URL to run the same tests on PostgreSQL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        eng = create_engine(url)
        Base.metadata.drop_all(eng)
    else:
        eng = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
            dbapi_conn.execute("PRAGMA foreign_keys=ON")  # SQLite ignores FKs unless asked

    Base.metadata.create_all(eng)
    # Background jobs open their own session through get_engine(): point them at the test DB.
    monkeypatch.setattr("app.db.session.get_engine", lambda: eng)
    yield eng
    if url:
        Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def app(engine: Engine) -> FastAPI:
    application = create_app()

    def override() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_db] = override
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


class Actor:
    """A registered, logged-in user plus convenience accessors."""

    def __init__(self, client: TestClient, email: str, name: str) -> None:
        r = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD, "display_name": name},
        )
        assert r.status_code == 201, r.text
        self.user = r.json()
        t = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert t.status_code == 200, t.text
        self.headers = {"Authorization": f"Bearer {t.json()['access_token']}"}
        self.email = email
        orgs = client.get("/api/v1/organizations", headers=self.headers).json()
        self.org_id: str = orgs[0]["id"]  # the personal organization created at registration


@pytest.fixture
def make_actor(client: TestClient):  # type: ignore[no-untyped-def]
    def _make(name: str) -> Actor:
        return Actor(client, f"{name.lower()}@example.com", name)

    return _make


@pytest.fixture
def limits(app: FastAPI, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Override settings (upload/row limits...) for both the API and the background jobs."""
    from app.core.config import get_settings

    def apply(**changes):  # type: ignore[no-untyped-def]
        settings = get_settings().model_copy(update=changes)
        app.dependency_overrides[get_settings] = lambda: settings
        monkeypatch.setattr("app.workers.dispatch.get_settings", lambda: settings)
        return settings

    return apply
