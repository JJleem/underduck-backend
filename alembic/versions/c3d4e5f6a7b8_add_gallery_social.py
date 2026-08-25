"""add gallery likes and comments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("gallery_like", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("artwork_id", sa.String(100), nullable=False), sa.Column("kakao_id", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("artwork_id", "kakao_id", name="uq_gallery_like_art_user"))
    op.create_index("ix_gallery_like_artwork_id", "gallery_like", ["artwork_id"])
    op.create_table("gallery_comment", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("artwork_id", sa.String(100), nullable=False), sa.Column("kakao_id", sa.String(64), nullable=False), sa.Column("author", sa.String(100), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True)))
    op.create_index("ix_gallery_comment_artwork_id", "gallery_comment", ["artwork_id"])

def downgrade():
    op.drop_index("ix_gallery_comment_artwork_id", table_name="gallery_comment"); op.drop_table("gallery_comment")
    op.drop_index("ix_gallery_like_artwork_id", table_name="gallery_like"); op.drop_table("gallery_like")
