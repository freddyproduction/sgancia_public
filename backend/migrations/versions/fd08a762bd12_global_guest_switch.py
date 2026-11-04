"""Disable guest links installation-wide by default, including existing installations."""
from alembic import op
import sqlalchemy as sa
revision='fd08a762bd12'
down_revision='fc07a762bd11'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('instance',sa.Column('guest_links_enabled',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.alter_column('instance','guest_links_enabled',server_default=None)

def downgrade():op.drop_column('instance','guest_links_enabled')
