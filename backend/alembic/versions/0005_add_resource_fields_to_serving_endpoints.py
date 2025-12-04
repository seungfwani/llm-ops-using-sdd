"""Add resource configuration fields to serving_endpoints table.

Revision ID: 0005_resource_fields
Revises: 0004_output_model_fields
Create Date: 2025-01-XX

This migration adds use_gpu, cpu_request, cpu_limit, memory_request, and memory_limit
fields to serving_endpoints table to store initial deployment settings for redeployment.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# NOTE: alembic_version.version_num is VARCHAR(32), so keep this <= 32 chars.
revision = "0005_resource_fields"
down_revision = "0004_output_model_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add resource configuration fields to serving_endpoints table."""
    op.add_column(
        "serving_endpoints",
        sa.Column("use_gpu", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "serving_endpoints",
        sa.Column("cpu_request", sa.Text(), nullable=True),
    )
    op.add_column(
        "serving_endpoints",
        sa.Column("cpu_limit", sa.Text(), nullable=True),
    )
    op.add_column(
        "serving_endpoints",
        sa.Column("memory_request", sa.Text(), nullable=True),
    )
    op.add_column(
        "serving_endpoints",
        sa.Column("memory_limit", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove resource configuration fields from serving_endpoints table."""
    op.drop_column("serving_endpoints", "memory_limit")
    op.drop_column("serving_endpoints", "memory_request")
    op.drop_column("serving_endpoints", "cpu_limit")
    op.drop_column("serving_endpoints", "cpu_request")
    op.drop_column("serving_endpoints", "use_gpu")

