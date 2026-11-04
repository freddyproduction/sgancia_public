"""Default dark theme for new accounts; preserve existing choices."""
from alembic import op
import sqlalchemy as sa
revision='f821a762bd22'
down_revision='f720a762bd21'
branch_labels=None
depends_on=None

def upgrade():op.alter_column('users','theme',existing_type=sa.String(5),server_default='dark')
def downgrade():op.alter_column('users','theme',existing_type=sa.String(5),server_default=None)
