"""add lounge_comment.parent_id (대댓글)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    # 깊이 1단까지만 쓴다. 기존 댓글은 NULL(최상위)로 남는다.
    op.add_column("lounge_comment", sa.Column("parent_id", sa.Integer()))
    op.create_index("ix_lounge_comment_parent_id", "lounge_comment", ["parent_id"])


def downgrade():
    op.drop_index("ix_lounge_comment_parent_id", table_name="lounge_comment")
    op.drop_column("lounge_comment", "parent_id")
