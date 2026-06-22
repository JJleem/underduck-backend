"""name_alias 테이블 (카카오 닉네임 → 로스터 실명)

Revision ID: 4225bee24349
Revises: a3f1c2d4e5b6
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4225bee24349'
down_revision: Union[str, None] = 'a3f1c2d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 초기 시드: 카카오 닉네임 → 로스터 실명
SEED = [
    ("성원", "백성원"),
    ("창의", "홍창의"),
    ("준수", "김준수"),
]


def upgrade() -> None:
    name_alias = op.create_table(
        'name_alias',
        sa.Column('kakao_name', sa.String(length=100), nullable=False),
        sa.Column('real_name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('kakao_name'),
    )
    op.bulk_insert(
        name_alias,
        [{"kakao_name": k, "real_name": v} for k, v in SEED],
    )


def downgrade() -> None:
    op.drop_table('name_alias')
