"""Operational controls, durable maintenance and revocable group invitations."""
from alembic import op
import sqlalchemy as sa
revision='f214a762bd16'
down_revision='f109a762bd15'
branch_labels=None
depends_on=None

def upgrade():
    for name in ('runtime_policy','backup_policy'):op.add_column('instance',sa.Column(name,sa.JSON,nullable=False,server_default='{}'))
    op.add_column('instance',sa.Column('telegram_config',sa.String(4000),nullable=True))
    from app.models import MaintenanceJob,ServiceHeartbeat
    MaintenanceJob.__table__.create(op.get_bind());ServiceHeartbeat.__table__.create(op.get_bind())
    op.add_column('group_invitations',sa.Column('id',sa.String(36),nullable=True))
    op.execute("UPDATE group_invitations SET id=md5(token_hash)")
    op.alter_column('group_invitations','id',nullable=False);op.create_unique_constraint('uq_group_invitation_id','group_invitations',['id'])
    for name in ('issuer_id','accepted_user_id'):op.add_column('group_invitations',sa.Column(name,sa.String(36),sa.ForeignKey('users.id'),nullable=True))
    op.add_column('participant_claims',sa.Column('issuer_id',sa.String(36),sa.ForeignKey('users.id'),nullable=True))

def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM maintenance_jobs) OR EXISTS(SELECT 1 FROM instance WHERE runtime_policy::text<>'{}' OR backup_policy::text<>'{}' OR telegram_config IS NOT NULL)")).scalar():raise RuntimeError('Conservare configurazioni e lavori prima del downgrade')
    op.drop_column('participant_claims','issuer_id')
    for name in ('issuer_id','accepted_user_id','id'):op.drop_column('group_invitations',name)
    op.drop_table('service_heartbeats');op.drop_table('maintenance_jobs')
    for name in ('telegram_config','backup_policy','runtime_policy'):op.drop_column('instance',name)
