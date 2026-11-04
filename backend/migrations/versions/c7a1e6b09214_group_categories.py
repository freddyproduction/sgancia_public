"""Persistent custom group categories."""
from alembic import op
import sqlalchemy as sa

revision = 'c7a1e6b09214'
down_revision = 'a739f391e8ca'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('categories',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('group_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('name_key', sa.String(180), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('group_id', 'name_key', name='uq_category_group_name'))
    op.create_index('ix_categories_group_id', 'categories', ['group_id'])


def downgrade():
    op.drop_index('ix_categories_group_id', table_name='categories')
    op.drop_table('categories')
