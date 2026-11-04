"""Account-wide theme preference."""
from alembic import op
import sqlalchemy as sa
revision='a18e9bf24601'
down_revision='f20ca7816b91'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('theme',sa.String(5),server_default='light',nullable=False))
    op.create_check_constraint('ck_users_theme','users',"theme in ('light','dark')")
    op.alter_column('users','theme',server_default=None)

def downgrade():
    op.drop_constraint('ck_users_theme','users',type_='check')
    op.drop_column('users','theme')
