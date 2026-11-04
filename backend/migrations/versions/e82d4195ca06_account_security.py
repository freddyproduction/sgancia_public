"""Account security, mail and private payment instructions."""
from alembic import op
import sqlalchemy as sa
revision='e82d4195ca06'
down_revision='d790e321ab04'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('instance',sa.Column('smtp_config',sa.String(16000)))
    for table,name,typ,default in [('instance','gate_enabled',sa.Boolean(),sa.true()),('users','email_verified',sa.Boolean(),sa.false()),('users','auth_version',sa.Integer(),'1'),('sessions','auth_version',sa.Integer(),'1')]:
        op.add_column(table,sa.Column(name,typ,nullable=False,server_default=default));op.alter_column(table,name,server_default=None)
    op.create_table('account_tokens',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('purpose',sa.String(16),nullable=False),sa.Column('email',sa.String(254),nullable=False),sa.Column('auth_version',sa.Integer(),nullable=False),sa.Column('expires',sa.BigInteger(),nullable=False),sa.Column('used',sa.Boolean(),nullable=False))
    op.create_index('ix_account_tokens_user_id','account_tokens',['user_id'])
    op.create_table('mail_messages',sa.Column('id',sa.String(36),primary_key=True),sa.Column('payload',sa.String(24000),nullable=False),sa.Column('token_hash',sa.String(64)),sa.Column('expires',sa.BigInteger(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('next_attempt',sa.BigInteger(),nullable=False),sa.Column('status',sa.String(16),nullable=False))
    op.create_table('payment_methods',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('payload',sa.String(24000),nullable=False),sa.Column('image',sa.LargeBinary()),sa.Column('shared',sa.Boolean(),nullable=False),sa.Column('version',sa.Integer(),nullable=False))
    op.create_index('ix_payment_methods_user_id','payment_methods',['user_id'])

def downgrade():
    for table in ('payment_methods','account_tokens','mail_messages'):
        if op.get_bind().execute(sa.text(f'SELECT count(*) FROM {table}')).scalar():raise RuntimeError('Conservare i dati account prima del downgrade')
        op.drop_table(table)
    op.drop_column('instance','smtp_config')
    for table,column in [('sessions','auth_version'),('users','auth_version'),('users','email_verified'),('instance','gate_enabled')]:op.drop_column(table,column)
