"""Encrypted import previews/provenance and opt-in guest export."""
from alembic import op
import sqlalchemy as sa
revision='fc07a762bd11'
down_revision='fb06a762bd10'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('guest_links',sa.Column('show_exports',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.alter_column('guest_links','show_exports',server_default=None)
    from app.models import ImportBatch,ImportedExpense
    ImportBatch.__table__.create(op.get_bind());ImportedExpense.__table__.create(op.get_bind())

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM import_batches) OR EXISTS(SELECT 1 FROM imported_expenses)')).scalar():raise RuntimeError('Esportare gli import prima del downgrade')
    op.drop_table('imported_expenses');op.drop_table('import_batches');op.drop_column('guest_links','show_exports')
