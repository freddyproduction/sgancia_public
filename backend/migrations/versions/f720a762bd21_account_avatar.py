"""Account image or icon."""
from alembic import op
import sqlalchemy as sa
revision='f720a762bd21'
down_revision='f619a762bd20'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('avatar',sa.LargeBinary(),nullable=True))
    op.add_column('users',sa.Column('avatar_icon',sa.String(16),nullable=False,server_default=''))
    op.add_column('users',sa.Column('avatar_version',sa.Integer(),nullable=False,server_default='1'))
    op.alter_column('users','avatar_icon',server_default=None)
    op.alter_column('users','avatar_version',server_default=None)

def downgrade():
    op.drop_column('users','avatar_version');op.drop_column('users','avatar_icon');op.drop_column('users','avatar')
