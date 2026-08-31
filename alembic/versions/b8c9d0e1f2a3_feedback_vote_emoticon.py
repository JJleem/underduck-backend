"""add emoticon to feedback and vote_comment (더덕티콘)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    # 사랑방(lounge_comment.emoticon)과 같은 id 체계. 기존 댓글은 NULL 로 남는다.
    op.add_column("feedback", sa.Column("emoticon", sa.String(50)))
    op.add_column("vote_comment", sa.Column("emoticon", sa.String(50)))


def downgrade():
    op.drop_column("vote_comment", "emoticon")
    op.drop_column("feedback", "emoticon")
