"""Multiple superadmins with an active anchor; explicit per-admin capabilities."""
from alembic import op
import sqlalchemy as sa
revision='f518a762bd19'
down_revision='f417a762bd18'
branch_labels=None
depends_on=None
USER_GUARD="""CREATE OR REPLACE FUNCTION sgancia_guard_superadmin_user() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  IF OLD.superadmin OR EXISTS(SELECT 1 FROM instance WHERE superadmin_id=OLD.id) THEN RAISE EXCEPTION 'Revocare prima il ruolo superadmin'; END IF;
  RETURN OLD;
 END IF;
 IF NEW.superadmin AND (NOT NEW.admin OR NEW.status<>'active') THEN RAISE EXCEPTION 'Il superadmin deve essere attivo e amministratore'; END IF;
 IF EXISTS(SELECT 1 FROM instance WHERE superadmin_id=OLD.id) AND (NEW.id<>OLD.id OR NOT NEW.admin OR NEW.status<>'active' OR NOT NEW.superadmin) THEN RAISE EXCEPTION 'Spostare prima il riferimento a un altro superadmin attivo'; END IF;
 IF OLD.superadmin AND NOT NEW.superadmin AND NOT EXISTS(SELECT 1 FROM users WHERE id<>OLD.id AND superadmin AND admin AND status='active') THEN RAISE EXCEPTION 'Ultimo superadmin protetto'; END IF;
 RETURN NEW;
END $$"""
INSTANCE_GUARD="""CREATE OR REPLACE FUNCTION sgancia_guard_superadmin_instance() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  IF OLD.superadmin_id IS NOT NULL THEN RAISE EXCEPTION 'Installazione protetta'; END IF;
  RETURN OLD;
 END IF;
 IF TG_OP='UPDATE' AND OLD.superadmin_id IS NOT NULL AND NEW.superadmin_id IS NULL THEN RAISE EXCEPTION 'Ultimo superadmin protetto'; END IF;
 IF NEW.superadmin_id IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.superadmin_id AND admin AND status='active') THEN RAISE EXCEPTION 'Superadmin non attivo'; END IF;
  IF TG_OP='UPDATE' AND OLD.superadmin_id IS NOT NULL AND NEW.superadmin_id<>OLD.superadmin_id AND NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.superadmin_id AND superadmin) THEN RAISE EXCEPTION 'Destinatario non superadmin'; END IF;
  UPDATE users SET superadmin=true WHERE id=NEW.superadmin_id AND NOT superadmin;
 END IF;
 RETURN NEW;
END $$"""

def upgrade():
 for name,typ,default in [('superadmin',sa.Boolean(),'false'),('requested_role',sa.String(16),"'user'")]:
  op.add_column('users',sa.Column(name,typ,nullable=False,server_default=sa.text(default)));op.alter_column('users',name,server_default=None)
 op.create_check_constraint('ck_users_superadmin_active','users',"not superadmin or (admin and status='active')")
 op.add_column('users',sa.Column('admin_permissions',sa.JSON(),nullable=True))
 op.add_column('invitations',sa.Column('requested_role',sa.String(16),nullable=False,server_default='user'));op.alter_column('invitations','requested_role',server_default=None)
 op.add_column('invitations',sa.Column('issuer_auth_version',sa.Integer(),nullable=True))
 op.execute('UPDATE users SET superadmin=true WHERE id IN (SELECT superadmin_id FROM instance WHERE superadmin_id IS NOT NULL)')
 if op.get_bind().dialect.name=='postgresql':op.execute(USER_GUARD);op.execute(INSTANCE_GUARD)

def downgrade():
 if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM users WHERE admin_permissions IS NOT NULL OR requested_role<>'user' OR (superadmin AND id NOT IN (SELECT superadmin_id FROM instance WHERE superadmin_id IS NOT NULL))) OR EXISTS(SELECT 1 FROM invitations WHERE requested_role<>'user')")).scalar():raise RuntimeError('Downgrade bloccato: conserverebbe privilegi non rappresentabili')
 if op.get_bind().dialect.name=='postgresql':
  import importlib
  old=importlib.import_module('migrations.versions.f913a762bd08_installation_superadmin');op.execute(old.USER_GUARD);op.execute(old.INSTANCE_GUARD)
 for name in ('issuer_auth_version','requested_role'):op.drop_column('invitations',name)
 op.drop_constraint('ck_users_superadmin_active','users',type_='check')
 for name in ('admin_permissions','requested_role','superadmin'):op.drop_column('users',name)
