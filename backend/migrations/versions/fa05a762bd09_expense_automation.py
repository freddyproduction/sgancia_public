"""Expense templates, durable recurrence jobs, advances."""
from alembic import op
import sqlalchemy as sa
revision='fa05a762bd09'
down_revision='f913a762bd08'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('settlements',sa.Column('kind',sa.String(20),nullable=False,server_default='reimbursement'))
    op.add_column('settlements',sa.Column('note',sa.String(2000),nullable=False,server_default=''))
    op.alter_column('settlements','kind',server_default=None)
    op.alter_column('settlements','note',server_default=None)
    from app.models import ExpensePlan,ExpenseJob
    ExpensePlan.__table__.create(op.get_bind())
    ExpenseJob.__table__.create(op.get_bind())

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT EXISTS(SELECT 1 FROM expense_plans)')).scalar():
        raise RuntimeError('Esportare i modelli e le ricorrenze prima del downgrade')
    op.drop_table('expense_jobs');op.drop_table('expense_plans')
    op.drop_column('settlements','note');op.drop_column('settlements','kind')
