"""Add dataset_versions table for data versioning integration.

Revision ID: 0011_dataset_versions
Revises: 0010_registry_models
Create Date: 2025-01-27

This migration creates the dataset_versions table to track dataset versions
managed by open-source versioning tools (e.g., DVC).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, BIGINT

# revision identifiers, used by Alembic.
revision = "0011_dataset_versions"
down_revision = "0010_registry_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create dataset_versions table."""
    op.create_table(
        "dataset_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_record_id", UUID(as_uuid=True), nullable=False),
        sa.Column("versioning_system", sa.Text(), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("parent_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("version_tag", sa.Text(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("diff_summary", JSONB, nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False, default=0),
        sa.Column("total_size_bytes", BIGINT, nullable=False, default=0),
        sa.Column("compression_ratio", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_record_id"],
            ["dataset_records.id"],
            ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["dataset_versions.id"],
            ondelete="SET NULL"
        ),
        sa.CheckConstraint("file_count >= 0", name="check_file_count"),
        sa.CheckConstraint("total_size_bytes >= 0", name="check_total_size"),
        sa.UniqueConstraint(
            "versioning_system", "version_id", "dataset_record_id",
            name="uq_versioning_system_version"
        )
    )
    op.create_index("idx_dataset_version_record_id", "dataset_versions", ["dataset_record_id"])
    op.create_index("idx_dataset_version_parent", "dataset_versions", ["parent_version_id"])
    op.create_index("idx_dataset_version_checksum", "dataset_versions", ["checksum"])


def downgrade() -> None:
    """Drop dataset_versions table."""
    op.drop_index("idx_dataset_version_checksum", table_name="dataset_versions")
    op.drop_index("idx_dataset_version_parent", table_name="dataset_versions")
    op.drop_index("idx_dataset_version_record_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")

