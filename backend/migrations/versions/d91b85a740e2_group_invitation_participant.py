"""Optional explicit link between invitation and existing virtual participant."""
from alembic import op
import sqlalchemy as sa
revision = 'd91b85a740e2'
down_revision = 'c7a1e6b09214'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('group_invitations',sa.Column('participant_id',sa.String(36),nullable=True))
    op.create_foreign_key('fk_group_invitation_participant','group_invitations','participants',['participant_id','group_id'],['id','group_id'])


def downgrade():
    op.drop_constraint('fk_group_invitation_participant','group_invitations',type_='foreignkey')
    op.drop_column('group_invitations','participant_id')
