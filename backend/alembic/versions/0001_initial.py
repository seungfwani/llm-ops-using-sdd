"""Initial schema aligned with specs/001-document-llm-ops/data-model.md."""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SQL_PATH = (
    Path(__file__).resolve()
    .parents[2]  # backend/alembic/versions -> backend
    .joinpath("src", "catalog", "migrations", "0001_initial.sql")
)


def upgrade() -> None:
    op.execute(SQL_PATH.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("This migration cannot be downgraded automatically.")

