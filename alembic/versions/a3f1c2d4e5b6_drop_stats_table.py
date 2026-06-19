"""drop stats table

stats는 더 이상 스냅샷 테이블을 읽지 않고 matches·mom_vote에서 실시간 집계한다
(routers/stats.py). 미사용 테이블을 제거한다.

Revision ID: a3f1c2d4e5b6
Revises: b16e13c75d2e
Create Date: 2026-06-19 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c2d4e5b6'
down_revision: Union[str, None] = 'b16e13c75d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('stats')


def downgrade() -> None:
    op.create_table(
        'stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('no', sa.String(length=10), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('pos', sa.String(length=20), nullable=True),
        sa.Column('apps', sa.Integer(), nullable=True),
        sa.Column('goals', sa.Integer(), nullable=True),
        sa.Column('assists', sa.Integer(), nullable=True),
        sa.Column('mom', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
