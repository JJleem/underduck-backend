"""kakao_id 가명화 — 원본 카카오 ID를 HMAC-SHA256 치환값(pid)으로 일괄 변환

카카오 원본 ID는 영구 식별자라 유출되면 회수가 불가능하다. DB에서 원본을 없애고
서버만 아는 pepper로 만든 단방향 pid만 남긴다.

되돌릴 수 없다(단방향 해시). 실행 전 DB 백업 필수:
    pg_dump underduck > ~/underduck-before-pseudonymize.sql

UNDERDUCK_ID_PEPPER 가 서버 .env 에 있어야 한다. 이 값을 분실하면 이후 로그인하는
회원이 기존 데이터와 연결되지 않는다(글·투표 소유권 소실).

Revision ID: c7d9e0f1a2b3
Revises: ba92c1852ad1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from security import is_pseudonym, pseudonymize

revision: str = "c7d9e0f1a2b3"
down_revision: Union[str, None] = "ba92c1852ad1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# kakao_id 를 신원으로 쓰는 테이블 전부
_TABLES = (
    "users",
    "attendance_vote",
    "vote_comment",
    "board_post",
    "board_comment",
    "board_like",
)


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        rows = conn.execute(
            sa.text(f"SELECT DISTINCT kakao_id FROM {table} WHERE kakao_id IS NOT NULL")  # noqa: S608
        ).scalars().all()

        # 이미 변환된 값은 건너뛴다 → 마이그레이션 재실행이 안전하다.
        pending = [v for v in rows if v and not is_pseudonym(v)]
        for original in pending:
            conn.execute(
                sa.text(f"UPDATE {table} SET kakao_id = :new WHERE kakao_id = :old"),  # noqa: S608
                {"new": pseudonymize(original), "old": original},
            )
        print(f"[pseudonymize] {table}: {len(pending)}건 변환 (전체 {len(rows)}건)")


def downgrade() -> None:
    raise RuntimeError(
        "kakao_id 가명화는 단방향 해시라 되돌릴 수 없습니다. "
        "복구가 필요하면 마이그레이션 전 pg_dump 백업에서 복원하세요."
    )
