"""Add registry_models table for model registry integration.

Revision ID: 0010_registry_models
Revises: 0009_workflow_pipelines
Create Date: 2025-01-27

This migration creates the registry_models table to track models imported
from or exported to open-source registries (e.g., Hugging Face Hub).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "0010_registry_models"
down_revision = "0009_workflow_pipelines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create registry_models table."""
    op.create_table(
        "registry_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model_catalog_id", UUID(as_uuid=True), nullable=False),
        sa.Column("registry_type", sa.Text(), nullable=False),
        sa.Column("registry_model_id", sa.Text(), nullable=False),
        sa.Column("registry_repo_url", sa.Text(), nullable=False),
        sa.Column("registry_version", sa.Text(), nullable=True),
        sa.Column("imported", sa.Boolean(), nullable=False, default=False),
        sa.Column("imported_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("exported_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("registry_metadata", JSONB, nullable=True),
        sa.Column("sync_status", sa.Text(), nullable=False, default="never_synced"),
        sa.Column("last_sync_check", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["model_catalog_id"],
            ["model_catalog_entries.id"],
            ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "sync_status in ('synced', 'out_of_sync', 'never_synced')",
            name="check_registry_sync_status"
        )
    )
    op.create_index("idx_registry_model_catalog_id", "registry_models", ["model_catalog_id"])
    op.create_index("idx_registry_model_registry", "registry_models", ["registry_type", "registry_model_id"])


def downgrade() -> None:
    """Drop registry_models table."""
    op.drop_index("idx_registry_model_registry", table_name="registry_models")
    op.drop_index("idx_registry_model_catalog_id", table_name="registry_models")
    op.drop_table("registry_models")

