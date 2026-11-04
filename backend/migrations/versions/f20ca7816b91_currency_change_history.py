"""Currency conversion history."""
from alembic import op
import sqlalchemy as sa
revision='f20ca7816b91'
down_revision='e49ac1072f63'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('currency_changes',sa.Column('id',sa.String(36),primary_key=True),sa.Column('group_id',sa.String(36),sa.ForeignKey('groups.id'),nullable=False),sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False))
    op.create_index('ix_currency_changes_group_id','currency_changes',['group_id'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM currency_changes')).scalar():raise RuntimeError('Conservare lo storico dei cambi prima del downgrade')
    op.drop_table('currency_changes')
