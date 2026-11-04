"""Private notification inbox and account/group preferences."""
from alembic import op
import sqlalchemy as sa
revision='ff09a762bd14'
down_revision='fe08a762bd13'
branch_labels=None
depends_on=None

def upgrade():
    from app.models import NotificationPreference,Notification
    NotificationPreference.__table__.create(op.get_bind())
    Notification.__table__.create(op.get_bind())

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM notifications) OR EXISTS(SELECT 1 FROM notification_preferences)')).scalar():
        raise RuntimeError('Conservare notifiche e preferenze prima del downgrade')
    op.drop_table('notifications');op.drop_table('notification_preferences')
