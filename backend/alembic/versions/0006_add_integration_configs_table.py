"""Add integration_configs table for open-source tool integration configuration.

Revision ID: 0006_integration_configs
Revises: 0005_resource_fields
Create Date: 2025-01-27

This migration creates the integration_configs table to store configuration
for open-source tool integrations (MLflow, KServe, Argo Workflows, etc.).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "0006_integration_configs"
down_revision = "0005_resource_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create integration_configs table."""
    op.create_table(
        "integration_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("integration_type", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("feature_flags", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "integration_type in ('experiment_tracking', 'serving', 'orchestration', 'registry', 'versioning')",
            name="check_integration_type"
        ),
        sa.CheckConstraint(
            "environment in ('dev', 'stg', 'prod')",
            name="check_environment"
        ),
    )
    op.create_index(
        "idx_integration_config_type_tool_env",
        "integration_configs",
        ["integration_type", "tool_name", "environment"],
        unique=True
    )


def downgrade() -> None:
    """Drop integration_configs table."""
    op.drop_index("idx_integration_config_type_tool_env", table_name="integration_configs")
    op.drop_table("integration_configs")

