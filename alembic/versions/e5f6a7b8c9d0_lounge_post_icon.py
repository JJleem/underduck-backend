"""add lounge_post.icon (노션식 페이지 아이콘)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    # 댓글 이모티콘과 같은 id 체계. 기존 글은 NULL(아이콘 없음)로 남는다.
    op.add_column("lounge_post", sa.Column("icon", sa.String(50)))


def downgrade():
    op.drop_column("lounge_post", "icon")
