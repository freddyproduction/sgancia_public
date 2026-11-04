"""Revocable Telegram identities, one-time linking, encrypted inbox and outbox."""
from alembic import op
import sqlalchemy as sa
revision='f311a762bd17'
down_revision='f214a762bd16'
branch_labels=None
depends_on=None
TABLES=('telegram_state','telegram_links','telegram_grants','telegram_updates','telegram_actions','telegram_outbox')

def upgrade():
    from app.db import Base
    from app import models
    for name in TABLES:Base.metadata.tables[name].create(op.get_bind())
    op.execute("INSERT INTO telegram_state(id,generation,\"offset\",username,verified_at,error) VALUES(1,0,0,'',0,'')")

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM telegram_links) OR EXISTS(SELECT 1 FROM telegram_updates) OR EXISTS(SELECT 1 FROM telegram_outbox)')).scalar():raise RuntimeError('Conservare e scollegare i dati Telegram prima del downgrade')
    for name in reversed(TABLES):op.drop_table(name)
