"""Add DeploymentSpec fields to serving_endpoints table.

Revision ID: 0013_add_deployment_spec
Revises: 0012_add_train_job_spec
Create Date: 2025-01-27

This migration adds DeploymentSpec fields to serving_endpoints table to support
training-serving-spec.md standardized structure. The deployment_spec field stores
the complete DeploymentSpec as JSONB for validation and conversion purposes.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0013_add_deployment_spec"
down_revision = "0012_add_train_job_spec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add DeploymentSpec fields to serving_endpoints table."""
    # Add deployment_spec JSONB field to store complete DeploymentSpec
    op.add_column(
        "serving_endpoints",
        sa.Column("deployment_spec", JSONB, nullable=True),
    )
    
    # Add index on deployment_spec for querying
    op.create_index(
        "idx_serving_endpoints_deployment_spec",
        "serving_endpoints",
        ["deployment_spec"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove DeploymentSpec fields from serving_endpoints table."""
    op.drop_index("idx_serving_endpoints_deployment_spec", table_name="serving_endpoints")
    op.drop_column("serving_endpoints", "deployment_spec")

