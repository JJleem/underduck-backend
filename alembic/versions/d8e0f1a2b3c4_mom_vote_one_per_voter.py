"""mom_vote 1인 1표 — 중복 정리 후 (match_id, voter_name, vote_type) UNIQUE

같은 사람이 한 경기 한 부문에 여러 번 투표할 수 있었다. 프론트는 DELETE → POST 로
갈아끼우고 있었지만 HTTP 2번으로 쪼개져 있어 경합이나 API 직접 호출로 표를 쌓을 수
있었다. 백엔드 POST가 upsert로 바뀌었으므로(routers/mom_vote.py) 여기서는 기존
중복을 정리하고 DB 차원의 backstop만 건다.

중복은 **가장 최근 표(최대 id)만 남기고** 삭제한다 — 갈아끼우기의 마지막 결과가
사용자가 의도한 표다.

Revision ID: d8e0f1a2b3c4
Revises: c7d9e0f1a2b3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e0f1a2b3c4"
down_revision: Union[str, None] = "c7d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "uq_mom_vote_match_voter_type"


def upgrade() -> None:
    conn = op.get_bind()

    dupes = conn.execute(sa.text("""
        SELECT count(*) FROM mom_vote m
        WHERE m.id < (
            SELECT max(x.id) FROM mom_vote x
            WHERE x.match_id  IS NOT DISTINCT FROM m.match_id
              AND x.voter_name IS NOT DISTINCT FROM m.voter_name
              AND x.vote_type  IS NOT DISTINCT FROM m.vote_type
        )
    """)).scalar_one()

    # 각 (경기, 투표자, 부문) 조합에서 최신 표만 남긴다.
    conn.execute(sa.text("""
        DELETE FROM mom_vote m
        WHERE m.id < (
            SELECT max(x.id) FROM mom_vote x
            WHERE x.match_id  IS NOT DISTINCT FROM m.match_id
              AND x.voter_name IS NOT DISTINCT FROM m.voter_name
              AND x.vote_type  IS NOT DISTINCT FROM m.vote_type
        )
    """))
    print(f"[mom_vote] 중복 {dupes}건 정리 (최신 표 유지)")

    op.create_unique_constraint(
        _CONSTRAINT, "mom_vote", ["match_id", "voter_name", "vote_type"]
    )


def downgrade() -> None:
    # 제약만 되돌린다. 정리된 중복 표는 복구하지 않는다(복구할 가치가 없는 데이터).
    op.drop_constraint(_CONSTRAINT, "mom_vote", type_="unique")
