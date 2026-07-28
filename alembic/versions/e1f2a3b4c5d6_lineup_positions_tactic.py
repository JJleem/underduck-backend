"""lineup 자유 배치 좌표 + 팀 전술 + 개인 전술

Revision ID: e1f2a3b4c5d6
Revises: d8e0f1a2b3c4
Create Date: 2026-07-28

positions는 NULL 허용 — 기존 라인업은 그대로 포메이션 프리셋 좌표로 그려진다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d8e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lineup", sa.Column("positions", sa.JSON(), nullable=True))
    op.add_column("lineup", sa.Column("tactic", sa.String(length=20), nullable=True))
    op.add_column("lineup", sa.Column("instructions", sa.JSON(), nullable=True))
    # 전술게시판: 글에 붙는 라인업 + 수정 시각
    op.add_column("board_post", sa.Column("lineup", sa.JSON(), nullable=True))
    op.add_column("board_post", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("board_post", "updated_at")
    op.drop_column("board_post", "lineup")
    op.drop_column("lineup", "instructions")
    op.drop_column("lineup", "tactic")
    op.drop_column("lineup", "positions")
