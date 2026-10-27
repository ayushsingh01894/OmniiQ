"""baseline (no tables yet)

Establishes the Alembic history. Phase 2 adds the first real tables on top of this revision.

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00
"""
from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
