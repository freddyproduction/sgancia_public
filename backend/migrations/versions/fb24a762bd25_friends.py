"""Friend requests and private revocable links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from app.models import Friendship,FriendLink
revision='fb24a762bd25'
down_revision='fa23a762bd24'
branch_labels=None
depends_on=None

def upgrade():
    if 'archival' not in {c['name'] for c in inspect(op.get_bind()).get_columns('users')}:
        op.add_column('users',sa.Column('archival',sa.Boolean(),nullable=False,server_default=sa.false()))
        op.alter_column('users','archival',server_default=None)
    if 'ck_users_archival' not in {c['name'] for c in inspect(op.get_bind()).get_check_constraints('users')}:
        op.create_check_constraint('ck_users_archival','users',"not archival or (deleted and not admin and not superadmin and status='suspended')")
    for model in (Friendship,FriendLink):
        if not inspect(op.get_bind()).has_table(model.__tablename__):model.__table__.create(op.get_bind())

def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM users WHERE archival LIMIT 1')).first():raise RuntimeError('Riferimenti storici backup presenti: downgrade non sicuro')
    op.drop_constraint('ck_users_archival','users',type_='check');op.drop_column('users','archival')
    for model in (FriendLink,Friendship):model.__table__.drop(op.get_bind())
