"""add enum values

Revision ID: 5b18ce3bad4d
Revises: 6851cefdd56
Create Date: 2025-06-02 22:26:08.400380

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b18ce3bad4d'
down_revision = '9a46a16aee21'
branch_labels = None
depends_on = None



def upgrade():
    # Добавляем новые значения в ENUM тип 'gamestatus'
    op.execute("ALTER TYPE gamestatus ADD VALUE IF NOT EXISTS 'HIDING_PHASE'")
    op.execute("ALTER TYPE gamestatus ADD VALUE IF NOT EXISTS 'SEARCHING_PHASE'")


def downgrade():
    pass
