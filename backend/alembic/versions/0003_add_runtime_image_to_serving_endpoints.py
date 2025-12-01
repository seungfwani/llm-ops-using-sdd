"""Add runtime_image column to serving_endpoints table.

Revision ID: 0003_add_runtime_image_to_serving_endpoints
Revises: 0002_add_storage_uri
Create Date: 2025-12-01

This migration adds the runtime_image field to record which serving runtime
image (e.g., vLLM, TGI, custom) is used per serving endpoint, aligning with
FR-006h.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# NOTE: alembic_version.version_num is VARCHAR(32), so keep this <= 32 chars.
revision = "0003_runtime_image"
down_revision = "0002_add_storage_uri"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add runtime_image column to serving_endpoints table."""
    op.add_column(
        "serving_endpoints",
        sa.Column("runtime_image", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove runtime_image column from serving_endpoints table."""
    op.drop_column("serving_endpoints", "runtime_image")


