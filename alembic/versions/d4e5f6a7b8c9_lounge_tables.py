"""add lounge (사랑방) posts and comments

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lounge_post",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kakao_id", sa.String(64), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("admin_reply", sa.Text()),
        sa.Column("admin_reply_author", sa.String(100)),
        sa.Column("admin_reply_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_lounge_post_kakao_id", "lounge_post", ["kakao_id"])

    op.create_table(
        "lounge_comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("kakao_id", sa.String(64), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("message", sa.Text()),
        # 이모티콘 id (그림 파일 이름). URL 이 아니라 id 만 둔다.
        sa.Column("emoticon", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_lounge_comment_post_id", "lounge_comment", ["post_id"])


def downgrade():
    op.drop_index("ix_lounge_comment_post_id", table_name="lounge_comment")
    op.drop_table("lounge_comment")
    op.drop_index("ix_lounge_post_kakao_id", table_name="lounge_post")
    op.drop_table("lounge_post")
