"""Add TrainJobSpec fields to training_jobs table.

Revision ID: 0012_add_train_job_spec
Revises: 0011_dataset_versions
Create Date: 2025-01-27

This migration adds TrainJobSpec fields to training_jobs table to support
training-serving-spec.md standardized structure. The train_job_spec field stores
the complete TrainJobSpec as JSONB for validation and conversion purposes.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0012_add_train_job_spec"
down_revision = "0011_dataset_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add TrainJobSpec fields to training_jobs table."""
    # Add train_job_spec JSONB field to store complete TrainJobSpec
    op.add_column(
        "training_jobs",
        sa.Column("train_job_spec", JSONB, nullable=True),
    )
    
    # Add index on train_job_spec for querying
    op.create_index(
        "idx_training_jobs_train_job_spec",
        "training_jobs",
        ["train_job_spec"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove TrainJobSpec fields from training_jobs table."""
    op.drop_index("idx_training_jobs_train_job_spec", table_name="training_jobs")
    op.drop_column("training_jobs", "train_job_spec")

