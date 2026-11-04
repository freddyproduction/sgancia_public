"""Private attachment metadata and optional Smart balances."""
from alembic import op
import sqlalchemy as sa
revision='b65d3ea41902'
down_revision='a18e9bf24601'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('groups',sa.Column('smart_balances',sa.Boolean(),server_default=sa.true(),nullable=False))
    op.alter_column('groups','smart_balances',server_default=None)
    op.add_column('guest_links',sa.Column('show_attachments',sa.Boolean(),server_default=sa.false(),nullable=False))
    op.alter_column('guest_links','show_attachments',server_default=None)
    op.create_table('attachments',sa.Column('id',sa.String(36),primary_key=True),sa.Column('group_id',sa.String(36),sa.ForeignKey('groups.id'),nullable=False),sa.Column('expense_id',sa.String(36)),sa.Column('settlement_id',sa.String(36),sa.ForeignKey('settlements.id')),sa.Column('expense_revision',sa.Integer()),sa.Column('uploader_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('storage_key',sa.String(40),unique=True,nullable=False),sa.Column('filename',sa.String(180),nullable=False),sa.Column('media_type',sa.String(60),nullable=False),sa.Column('size',sa.BigInteger(),nullable=False),sa.Column('preview_size',sa.BigInteger(),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),sa.Column('deleted',sa.Boolean(),nullable=False),sa.Column('created',sa.BigInteger(),nullable=False),sa.ForeignKeyConstraint(['expense_id','expense_revision'],['expense_versions.expense_id','expense_versions.version']),sa.CheckConstraint('(expense_id IS NOT NULL AND settlement_id IS NULL AND expense_revision IS NOT NULL) OR (expense_id IS NULL AND settlement_id IS NOT NULL AND expense_revision IS NULL)',name='ck_attachment_parent'),sa.CheckConstraint('size > 0 AND preview_size >= 0',name='ck_attachment_size'))
    for column in ('group_id','expense_id','settlement_id'):op.create_index('ix_attachments_'+column,'attachments',[column])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM attachments')).scalar():raise RuntimeError('Preservare gli allegati e i metadati prima del downgrade')
    op.drop_table('attachments')
    op.drop_column('guest_links','show_attachments')
    op.drop_column('groups','smart_balances')
