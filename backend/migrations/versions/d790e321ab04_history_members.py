"""History, disputes and controlled membership operations."""
from alembic import op
import sqlalchemy as sa
revision='d790e321ab04'
down_revision='c4816f2ab903'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('participants',sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.alter_column('participants','active',server_default=None)
    op.add_column('participants',sa.Column('merged_into',sa.String(36)))
    op.add_column('settlement_events',sa.Column('reason',sa.String(2000),nullable=False,server_default=''))
    op.alter_column('settlement_events','reason',server_default=None)
    op.add_column('settlement_events',sa.Column('ordinal',sa.BigInteger(),nullable=False,server_default='0'))
    op.alter_column('settlement_events','ordinal',server_default=None)
    op.create_table('expense_disputes',sa.Column('id',sa.String(36),primary_key=True),sa.Column('expense_id',sa.String(36),sa.ForeignKey('expenses.id'),nullable=False),sa.Column('participant_id',sa.String(36),sa.ForeignKey('participants.id'),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('reason',sa.String(2000),nullable=False),sa.Column('status',sa.String(16),nullable=False),sa.Column('resolution',sa.String(2000),nullable=False),sa.Column('resolver_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('created',sa.BigInteger(),nullable=False),sa.Column('resolved_at',sa.BigInteger()),sa.CheckConstraint("status in ('open','resolved','rejected','withdrawn')",name='ck_expense_dispute_status'))
    op.create_index('ix_expense_disputes_expense_id','expense_disputes',['expense_id'])
    op.create_table('group_operations',sa.Column('id',sa.String(36),primary_key=True),sa.Column('group_id',sa.String(36),sa.ForeignKey('groups.id'),nullable=False),sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('kind',sa.String(30),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False))
    op.create_index('ix_group_operations_group_id','group_operations',['group_id'])
    op.create_table('virtual_delegations',sa.Column('id',sa.String(36),primary_key=True),sa.Column('group_id',sa.String(36),sa.ForeignKey('groups.id'),nullable=False),sa.Column('virtual_id',sa.String(36),sa.ForeignKey('participants.id'),nullable=False),sa.Column('delegate_id',sa.String(36),sa.ForeignKey('participants.id'),nullable=False),sa.Column('pay',sa.Boolean(),nullable=False),sa.Column('attest',sa.Boolean(),nullable=False),sa.Column('expires',sa.BigInteger(),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False),sa.Column('granted_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False))
    op.create_index('ix_virtual_delegations_group_id','virtual_delegations',['group_id'])

def downgrade():
    for table in ('expense_disputes','group_operations','virtual_delegations'):
        if op.get_bind().execute(sa.text(f'SELECT count(*) FROM {table}')).scalar():raise RuntimeError('Esportare i nuovi eventi prima del downgrade')
    for table in ('virtual_delegations','group_operations','expense_disputes'):op.drop_table(table)
    op.drop_column('settlement_events','ordinal')
    op.drop_column('settlement_events','reason')
    op.drop_column('participants','merged_into');op.drop_column('participants','active')
