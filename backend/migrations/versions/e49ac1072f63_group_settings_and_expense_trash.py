"""Group presentation settings and reversible expense deletion."""
from alembic import op
import sqlalchemy as sa
revision='e49ac1072f63'
down_revision='d91b85a740e2'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('groups',sa.Column('description',sa.String(2000),server_default='',nullable=False))
    op.add_column('groups',sa.Column('icon',sa.String(16),server_default='✳',nullable=False))
    op.add_column('groups',sa.Column('image',sa.LargeBinary(),nullable=True))
    op.add_column('groups',sa.Column('metadata_version',sa.Integer(),server_default='1',nullable=False))
    op.add_column('expenses',sa.Column('deleted',sa.Boolean(),server_default=sa.false(),nullable=False))
    for column in ('description','icon','metadata_version'):
        op.alter_column('groups',column,server_default=None)
    op.alter_column('expenses','deleted',server_default=None)


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM expenses WHERE deleted')).scalar():
        raise RuntimeError('Ripristinare prima le spese nel cestino per effettuare il downgrade')
    op.drop_column('expenses','deleted')
    for column in ('metadata_version','image','icon','description'):
        op.drop_column('groups',column)
