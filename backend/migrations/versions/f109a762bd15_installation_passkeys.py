"""Independent passkeys for the installation gate."""
from alembic import op
import sqlalchemy as sa
revision='f109a762bd15'
down_revision='ff09a762bd14'
branch_labels=None
depends_on=None

def upgrade():
    from app.models import InstallationPasskey,InstallationChallenge
    InstallationPasskey.__table__.create(op.get_bind());InstallationChallenge.__table__.create(op.get_bind())
    op.add_column('gate_grants',sa.Column('credential_id',sa.String(1400),nullable=True))

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM installation_passkeys)')).scalar():raise RuntimeError('Rimuovere le passkey installazione prima del downgrade')
    op.drop_column('gate_grants','credential_id');op.drop_table('installation_challenges');op.drop_table('installation_passkeys')
