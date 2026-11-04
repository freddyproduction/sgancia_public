"""Reversible group deletion."""
from alembic import op
import sqlalchemy as sa
revision='c4816f2ab903'
down_revision='b65d3ea41902'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('groups',sa.Column('deleted',sa.Boolean(),server_default=sa.false(),nullable=False))
    op.alter_column('groups','deleted',server_default=None)

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM groups WHERE deleted')).scalar():raise RuntimeError('Ripristinare i gruppi nel cestino prima del downgrade')
    op.drop_column('groups','deleted')
