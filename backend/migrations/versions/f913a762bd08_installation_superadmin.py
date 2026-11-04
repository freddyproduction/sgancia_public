"""Immutable installation founder; no hard-coded name or address."""
import os,time,uuid
from alembic import op
import sqlalchemy as sa
revision='f913a762bd08'
down_revision='e82d4195ca06'
branch_labels=None
depends_on=None

USER_GUARD='''CREATE OR REPLACE FUNCTION sgancia_guard_superadmin_user() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM instance WHERE superadmin_id=OLD.id) THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Superadmin protetto: account non eliminabile'; END IF;
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.admin IS DISTINCT FROM TRUE OR NEW.status IS DISTINCT FROM 'active' THEN
   RAISE EXCEPTION 'Superadmin protetto: identità, ruolo e stato non rimovibili';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$'''
INSTANCE_GUARD='''CREATE OR REPLACE FUNCTION sgancia_guard_superadmin_instance() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  IF OLD.superadmin_id IS NOT NULL THEN RAISE EXCEPTION 'Superadmin protetto: installazione non eliminabile'; END IF;
  RETURN OLD;
 END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.superadmin_id IS NOT NULL AND NEW.superadmin_id IS DISTINCT FROM OLD.superadmin_id THEN
   RAISE EXCEPTION 'Superadmin protetto: fondatore non sostituibile';
  END IF;
 END IF;
 IF NEW.superadmin_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM users WHERE id=NEW.superadmin_id AND admin=TRUE AND status='active') THEN
  RAISE EXCEPTION 'Il superadmin deve essere un amministratore globale attivo';
 END IF;
 RETURN NEW;
END $$'''

def install_guards(bind):
    if bind.dialect.name!='postgresql':return
    bind.execute(sa.text(USER_GUARD));bind.execute(sa.text(INSTANCE_GUARD))
    bind.execute(sa.text('CREATE TRIGGER sgancia_superadmin_user BEFORE UPDATE OR DELETE ON users FOR EACH ROW EXECUTE FUNCTION sgancia_guard_superadmin_user()'))
    bind.execute(sa.text('CREATE TRIGGER sgancia_superadmin_instance BEFORE INSERT OR UPDATE OR DELETE ON instance FOR EACH ROW EXECUTE FUNCTION sgancia_guard_superadmin_instance()'))

def upgrade():
    op.add_column('instance',sa.Column('superadmin_id',sa.String(36)))
    op.create_foreign_key('fk_instance_superadmin','instance','users',['superadmin_id'],['id'],ondelete='RESTRICT')
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM instance')).scalar():
        chosen=os.environ.get('SGANCIA_LEGACY_SUPERADMIN_ID','').strip()
        admins=list(bind.execute(sa.text("SELECT id FROM users WHERE admin=TRUE AND status='active' AND NOT EXISTS (SELECT 1 FROM audit_events WHERE event='global_admin.granted' AND resource=users.id)" )).scalars())
        if not chosen and len(admins)==1:chosen=admins[0]
        if not chosen or not bind.execute(sa.text("SELECT count(*) FROM users WHERE id=:id AND admin=TRUE AND status='active'"),{'id':chosen}).scalar():
            raise RuntimeError('Primo amministratore non identificabile senza ambiguità: specificare SGANCIA_LEGACY_SUPERADMIN_ID con l’ID del fondatore verificato. Nessun nome/email viene usato per assegnare il ruolo.')
        bind.execute(sa.text('UPDATE instance SET superadmin_id=:id WHERE id=1'),{'id':chosen})
        bind.execute(sa.text("INSERT INTO audit_events (id,actor,event,resource,at) VALUES (:audit,NULL,'installation.superadmin_assigned',:id,:at)"),{'audit':uuid.uuid4().hex,'id':chosen,'at':int(time.time())})
    install_guards(bind)

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM instance WHERE superadmin_id IS NOT NULL')).scalar():raise RuntimeError('Downgrade bloccato: non rimuovere la protezione del superadmin di un’installazione inizializzata')
    if bind.dialect.name=='postgresql':
        for trigger,table in [('sgancia_superadmin_user','users'),('sgancia_superadmin_instance','instance')]:op.execute(f'DROP TRIGGER IF EXISTS {trigger} ON {table}')
        op.execute('DROP FUNCTION IF EXISTS sgancia_guard_superadmin_user()');op.execute('DROP FUNCTION IF EXISTS sgancia_guard_superadmin_instance()')
    op.drop_constraint('fk_instance_superadmin','instance',type_='foreignkey');op.drop_column('instance','superadmin_id')
