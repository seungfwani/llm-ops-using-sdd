"""Add model_family and dataset type fields

Revision ID: 0014
Revises: 0013
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013_add_deployment_spec'
branch_labels = None
depends_on = None


def upgrade():
    # Add model_family column to model_catalog_entries (nullable first, will be made required in next migration)
    op.add_column(
        'model_catalog_entries',
        sa.Column('model_family', sa.Text(), nullable=True, comment='Model family from training-serving-spec.md whitelist (llama, mistral, gemma, bert, etc.) - Required for TrainJobSpec/DeploymentSpec validation')
    )
    
    # Add type column to dataset_records (nullable first, will be made required in next migration)
    op.add_column(
        'dataset_records',
        sa.Column('type', sa.Text(), nullable=True, comment='Dataset type from training-serving-spec.md (pretrain_corpus, sft_pair, rag_qa, rlhf_pair) - Required for TrainJobSpec validation')
    )


def downgrade():
    # Remove model_family column from model_catalog_entries
    op.drop_column('model_catalog_entries', 'model_family')
    
    # Remove type column from dataset_records
    op.drop_column('dataset_records', 'type')

