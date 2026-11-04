"""Personal/public budgets and private final reports."""
from alembic import op
import sqlalchemy as sa
revision='fb06a762bd10'
down_revision='fa05a762bd09'
branch_labels=None
depends_on=None

def upgrade():
    from app.models import Budget,FinalReport
    Budget.__table__.create(op.get_bind());FinalReport.__table__.create(op.get_bind())

def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM budgets) OR EXISTS(SELECT 1 FROM final_reports)')).scalar():raise RuntimeError('Esportare budget e riepiloghi prima del downgrade')
    op.drop_table('final_reports');op.drop_table('budgets')
