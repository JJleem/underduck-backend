"""add lounge_like (글 좋아요)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    # kakao_id 는 중복 방지용이다 — 누가 눌렀는지 돌려주는 엔드포인트는 없다.
    op.create_table(
        "lounge_like",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("kakao_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("post_id", "kakao_id", name="uq_lounge_like_post_user"),
    )
    op.create_index("ix_lounge_like_post_id", "lounge_like", ["post_id"])


def downgrade():
    op.drop_index("ix_lounge_like_post_id", table_name="lounge_like")
    op.drop_table("lounge_like")
