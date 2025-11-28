"""Add storage_uri column to model_catalog_entries table.

Revision ID: 0002_add_storage_uri
Revises: 0001_initial
Create Date: 2025-01-15

This migration adds the storage_uri field to support model file uploads
per FR-001a. The field is nullable to support metadata-only catalog entries.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_storage_uri"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add storage_uri column to model_catalog_entries table."""
    op.add_column(
        "model_catalog_entries",
        sa.Column("storage_uri", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove storage_uri column from model_catalog_entries table."""
    op.drop_column("model_catalog_entries", "storage_uri")

