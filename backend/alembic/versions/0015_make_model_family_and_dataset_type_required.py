"""Make model_family and dataset type required fields

Revision ID: 0015
Revises: 0014
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    # Set default values for existing records before making columns NOT NULL
    # For model_family: set to 'unknown' for existing records (they will need to be updated)
    op.execute("""
        UPDATE model_catalog_entries 
        SET model_family = 'unknown' 
        WHERE model_family IS NULL
    """)
    
    # For dataset type: set to 'sft_pair' as default (most common type)
    op.execute("""
        UPDATE dataset_records 
        SET type = 'sft_pair' 
        WHERE type IS NULL
    """)
    
    # Now make columns NOT NULL
    op.alter_column(
        'model_catalog_entries',
        'model_family',
        nullable=False,
        existing_type=sa.Text(),
        existing_comment='Model family from training-serving-spec.md whitelist (llama, mistral, gemma, bert, etc.) - Required for TrainJobSpec/DeploymentSpec validation'
    )
    
    op.alter_column(
        'dataset_records',
        'type',
        nullable=False,
        existing_type=sa.Text(),
        existing_comment='Dataset type from training-serving-spec.md (pretrain_corpus, sft_pair, rag_qa, rlhf_pair) - Required for TrainJobSpec validation'
    )


def downgrade():
    # Make columns nullable again
    op.alter_column(
        'model_catalog_entries',
        'model_family',
        nullable=True,
        existing_type=sa.Text()
    )
    
    op.alter_column(
        'dataset_records',
        'type',
        nullable=True,
        existing_type=sa.Text()
    )

