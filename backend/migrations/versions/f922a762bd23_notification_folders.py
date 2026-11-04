"""Personal inbox archive and recoverable trash."""
from alembic import op
import sqlalchemy as sa
revision='f922a762bd23'
down_revision='f821a762bd22'
branch_labels=None
depends_on=None

def upgrade():
    # Older bootstrap migration creates this table from current metadata on fresh installs.
    inspector=sa.inspect(op.get_bind())
    if 'folder' not in {c['name'] for c in inspector.get_columns('notifications')}:
        op.add_column('notifications',sa.Column('folder',sa.String(16),nullable=False,server_default='inbox'))
    op.alter_column('notifications','folder',server_default=None)
    if 'ck_notification_folder' not in {c['name'] for c in inspector.get_check_constraints('notifications')}:
        op.create_check_constraint('ck_notification_folder','notifications',"folder in ('inbox','archived','trash')")

def downgrade():
    op.drop_constraint('ck_notification_folder','notifications',type_='check');op.drop_column('notifications','folder')
