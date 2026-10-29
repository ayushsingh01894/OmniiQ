"""Alembic history must apply, roll back, and match the SQLAlchemy models exactly."""

import os
import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

import app.models  # noqa: F401
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic(db_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_upgrade_head_then_downgrade_base(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    assert "0003" in (_alembic(url, "current").stdout + _alembic(url, "current").stderr)
    down = _alembic(url, "downgrade", "base")
    assert down.returncode == 0, down.stderr


def test_single_migration_head():
    heads = _alembic("sqlite://", "heads")
    assert heads.returncode == 0, heads.stderr
    assert (heads.stdout + heads.stderr).count("(head)") == 1


def test_migrations_create_exactly_the_model_schema(tmp_path):
    """If someone edits a model and forgets the migration, this fails."""
    url = f"sqlite:///{tmp_path / 'drift.db'}"
    assert _alembic(url, "upgrade", "head").returncode == 0
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations disagree: {diff}"
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "organizations",
        "organization_members",
        "projects",
        "audit_logs",
        "datasets",
        "dataset_versions",
        "data_jobs",
    } <= tables
