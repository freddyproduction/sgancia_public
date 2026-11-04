"""Reusable role-specific group invitation codes."""
from alembic import op
import sqlalchemy as sa
revision='f619a762bd20'
down_revision='f518a762bd19'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('group_join_codes',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('group_id',sa.String(36),sa.ForeignKey('groups.id',ondelete='CASCADE'),nullable=False),sa.Column('role',sa.String(16),nullable=False),sa.Column('secret',sa.LargeBinary(),nullable=False),sa.UniqueConstraint('group_id','role'),sa.CheckConstraint("role in ('admin','member','viewer')"))
    op.create_index('ix_group_join_codes_group_id','group_join_codes',['group_id'])

def downgrade():
    op.drop_table('group_join_codes')
