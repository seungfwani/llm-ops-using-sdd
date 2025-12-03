"""Add output_model_storage_uri and output_model_entry_id columns to training_jobs table.

Revision ID: 0004_output_model_fields
Revises: 0003_runtime_image
Create Date: 2025-12-01

This migration adds fields to track output models from completed training jobs:
- output_model_storage_uri: Storage URI where trained model artifacts are stored
- output_model_entry_id: Reference to the model catalog entry created from this training job
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# NOTE: alembic_version.version_num is VARCHAR(32), so keep this <= 32 chars.
revision = "0004_output_model_fields"
down_revision = "0003_runtime_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add output_model_storage_uri and output_model_entry_id columns to training_jobs table."""
    # Add output_model_storage_uri column
    op.add_column(
        "training_jobs",
        sa.Column("output_model_storage_uri", sa.Text(), nullable=True),
    )
    
    # Add output_model_entry_id column with foreign key constraint
    op.add_column(
        "training_jobs",
        sa.Column(
            "output_model_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_catalog_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove output_model_storage_uri and output_model_entry_id columns from training_jobs table."""
    op.drop_column("training_jobs", "output_model_entry_id")
    op.drop_column("training_jobs", "output_model_storage_uri")

