"""Add experiment_runs table for experiment tracking integration.

Revision ID: 0007_experiment_runs
Revises: 0006_integration_configs
Create Date: 2025-01-27

This migration creates the experiment_runs table to track training job
experiments in open-source tracking systems (e.g., MLflow).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "0007_experiment_runs"
down_revision = "0006_integration_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create experiment_runs table."""
    op.create_table(
        "experiment_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("training_job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tracking_system", sa.Text(), nullable=False),
        sa.Column("tracking_run_id", sa.Text(), nullable=False),
        sa.Column("experiment_name", sa.Text(), nullable=False),
        sa.Column("run_name", sa.Text(), nullable=True),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("artifact_uris", JSONB, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, default="running"),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["training_job_id"],
            ["training_jobs.id"],
            ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status in ('running', 'completed', 'failed', 'killed')",
            name="check_experiment_run_status"
        ),
        sa.UniqueConstraint("tracking_system", "tracking_run_id", name="uq_tracking_system_run_id")
    )
    op.create_index("idx_experiment_run_training_job_id", "experiment_runs", ["training_job_id"])
    op.create_index("idx_experiment_run_tracking_system_run_id", "experiment_runs", ["tracking_system", "tracking_run_id"])
    op.create_index("idx_experiment_run_status", "experiment_runs", ["status"])


def downgrade() -> None:
    """Drop experiment_runs table."""
    op.drop_index("idx_experiment_run_status", table_name="experiment_runs")
    op.drop_index("idx_experiment_run_tracking_system_run_id", table_name="experiment_runs")
    op.drop_index("idx_experiment_run_training_job_id", table_name="experiment_runs")
    op.drop_table("experiment_runs")

