"""Add workflow_pipelines table for workflow orchestration integration.

Revision ID: 0009_workflow_pipelines
Revises: 0008_serving_deployments
Create Date: 2025-01-27

This migration creates the workflow_pipelines table to track multi-stage
pipelines in open-source orchestration systems (e.g., Argo Workflows).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "0009_workflow_pipelines"
down_revision = "0008_serving_deployments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workflow_pipelines table."""
    op.create_table(
        "workflow_pipelines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_name", sa.Text(), nullable=False),
        sa.Column("orchestration_system", sa.Text(), nullable=False),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("workflow_namespace", sa.Text(), nullable=False),
        sa.Column("pipeline_definition", JSONB, nullable=False),
        sa.Column("stages", JSONB, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, default="pending"),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("max_retries", sa.Integer(), nullable=False, default=3),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="check_workflow_pipeline_status"
        ),
        sa.CheckConstraint("retry_count >= 0", name="check_retry_count"),
        sa.CheckConstraint("max_retries >= 0", name="check_max_retries"),
        sa.UniqueConstraint(
            "orchestration_system", "workflow_id", "workflow_namespace",
            name="uq_orchestration_workflow"
        )
    )
    op.create_index("idx_workflow_pipeline_status", "workflow_pipelines", ["status"])
    op.create_index(
        "idx_workflow_pipeline_orchestration_workflow",
        "workflow_pipelines",
        ["orchestration_system", "workflow_id", "workflow_namespace"]
    )


def downgrade() -> None:
    """Drop workflow_pipelines table."""
    op.drop_index("idx_workflow_pipeline_orchestration_workflow", table_name="workflow_pipelines")
    op.drop_index("idx_workflow_pipeline_status", table_name="workflow_pipelines")
    op.drop_table("workflow_pipelines")

