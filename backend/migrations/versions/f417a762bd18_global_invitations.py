"""Global invitation lifecycle metadata without storing clear invitation codes."""
from alembic import op
import sqlalchemy as sa
import uuid
revision='f417a762bd18'
down_revision='f311a762bd17'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('invitations',sa.Column('id',sa.String(36),nullable=True))
    for row in op.get_bind().execute(sa.text('SELECT token_hash FROM invitations')).all():
        op.get_bind().execute(sa.text('UPDATE invitations SET id=:id WHERE token_hash=:hash'),{'id':str(uuid.uuid4()),'hash':row[0]})
    op.alter_column('invitations','id',nullable=False)
    op.create_unique_constraint('uq_invitations_id','invitations',['id'])
    for name,typ,default in [('created',sa.BigInteger(),'0'),('revoked',sa.Boolean(),'false'),('version',sa.Integer(),'1')]:
        op.add_column('invitations',sa.Column(name,typ,nullable=False,server_default=sa.text(default)))
        op.alter_column('invitations',name,server_default=None)
    for name in ('issuer_id','used_by'):
        op.add_column('invitations',sa.Column(name,sa.String(36),nullable=True))
        op.create_foreign_key('fk_invitations_'+name,'invitations','users',[name],['id'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM invitations WHERE revoked OR version>1)')).scalar():raise RuntimeError('Downgrade non consentito: perderebbe le revoche o i rinnovi degli inviti')
    for name in ('issuer_id','used_by'):op.drop_constraint('fk_invitations_'+name,'invitations',type_='foreignkey');op.drop_column('invitations',name)
    op.drop_constraint('uq_invitations_id','invitations',type_='unique')
    for name in ('id','created','revoked','version'):op.drop_column('invitations',name)
