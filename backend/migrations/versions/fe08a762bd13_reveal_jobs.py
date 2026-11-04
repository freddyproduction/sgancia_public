"""Permission-scoped durable reveal jobs."""
from alembic import op
import sqlalchemy as sa
revision='fe08a762bd13'
down_revision='fd08a762bd12'
branch_labels=None
depends_on=None

def upgrade():
    from app.models import RevealJob
    RevealJob.__table__.create(op.get_bind())

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM reveal_jobs)')).scalar():raise RuntimeError('Esportare le programmazioni prima del downgrade')
    op.drop_table('reveal_jobs')
