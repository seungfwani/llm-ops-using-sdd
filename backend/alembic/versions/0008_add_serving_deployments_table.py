"""Add serving_deployments table for serving framework integration.

Revision ID: 0008_serving_deployments
Revises: 0007_experiment_runs
Create Date: 2025-01-27

This migration creates the serving_deployments table to track model serving
deployments through open-source frameworks (e.g., KServe, Ray Serve).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "0008_serving_deployments"
down_revision = "0007_experiment_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create serving_deployments table."""
    op.create_table(
        "serving_deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("serving_endpoint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("serving_framework", sa.Text(), nullable=False),
        sa.Column("framework_resource_id", sa.Text(), nullable=False),
        sa.Column("framework_namespace", sa.Text(), nullable=False),
        sa.Column("replica_count", sa.Integer(), nullable=False, default=1),
        sa.Column("min_replicas", sa.Integer(), nullable=False, default=1),
        sa.Column("max_replicas", sa.Integer(), nullable=False, default=1),
        sa.Column("autoscaling_metrics", JSONB, nullable=True),
        sa.Column("resource_requests", JSONB, nullable=True),
        sa.Column("resource_limits", JSONB, nullable=True),
        sa.Column("framework_status", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["serving_endpoint_id"],
            ["serving_endpoints.id"],
            ondelete="CASCADE"
        ),
        sa.CheckConstraint("min_replicas >= 0", name="check_min_replicas"),
        sa.CheckConstraint("max_replicas >= min_replicas", name="check_max_replicas"),
        sa.CheckConstraint("replica_count >= min_replicas AND replica_count <= max_replicas", name="check_replica_count"),
        sa.UniqueConstraint(
            "serving_framework", "framework_resource_id", "framework_namespace",
            name="uq_framework_resource"
        )
    )
    op.create_index("idx_serving_deployment_endpoint_id", "serving_deployments", ["serving_endpoint_id"])
    op.create_index(
        "idx_serving_deployment_framework_resource",
        "serving_deployments",
        ["serving_framework", "framework_resource_id", "framework_namespace"]
    )


def downgrade() -> None:
    """Drop serving_deployments table."""
    op.drop_index("idx_serving_deployment_framework_resource", table_name="serving_deployments")
    op.drop_index("idx_serving_deployment_endpoint_id", table_name="serving_deployments")
    op.drop_table("serving_deployments")

