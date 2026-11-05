"""Shared platform invitations and root-managed suspension/deletion."""
import importlib
from alembic import op
import sqlalchemy as sa
revision='fa23a762bd24'
down_revision='f922a762bd23'
branch_labels=None
depends_on=None
OLD=importlib.import_module('migrations.versions.f518a762bd19_authority')
USER_GUARD=OLD.USER_GUARD.replace("NEW.status<>'active') THEN RAISE EXCEPTION 'Il superadmin deve essere attivo e amministratore'", "NEW.deleted OR NEW.status NOT IN ('active','suspended')) THEN RAISE EXCEPTION 'Il superadmin deve essere amministratore attivo o sospeso'").replace("IF OLD.superadmin AND NOT NEW.superadmin AND NOT EXISTS", "IF OLD.superadmin AND OLD.status='active' AND (NOT NEW.superadmin OR NEW.status<>'active') AND NOT EXISTS")

USER_GUARD=USER_GUARD.replace("AND status='active') THEN","AND status='active' AND NOT deleted) THEN")

def upgrade():
    from app.models import PlatformInvitationLink
    PlatformInvitationLink.__table__.create(op.get_bind())
    if 'deleted' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}:
        op.add_column('users',sa.Column('deleted',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.alter_column('users','deleted',server_default=None)
    op.drop_constraint('ck_users_superadmin_active','users',type_='check')
    op.create_check_constraint('ck_users_superadmin_active','users',"not superadmin or (admin and not deleted and status in ('active','suspended'))")
    if 'ck_users_deleted' not in {c['name'] for c in sa.inspect(op.get_bind()).get_check_constraints('users')}:op.create_check_constraint('ck_users_deleted','users',"not deleted or (not admin and not superadmin and status='suspended')")
    if op.get_bind().dialect.name=='postgresql':op.execute(USER_GUARD)

def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM users WHERE deleted OR (superadmin AND status<>'active')) OR EXISTS(SELECT 1 FROM platform_invitation_links)")).scalar():raise RuntimeError('Conservare link e account eliminati o sospesi prima del downgrade')
    if op.get_bind().dialect.name=='postgresql':op.execute(OLD.USER_GUARD)
    op.drop_constraint('ck_users_superadmin_active','users',type_='check')
    op.create_check_constraint('ck_users_superadmin_active','users',"not superadmin or (admin and status='active')")
    op.drop_constraint('ck_users_deleted','users',type_='check')
    op.drop_column('users','deleted');op.drop_table('platform_invitation_links')
