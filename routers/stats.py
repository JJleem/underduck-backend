from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Match, MomVote, Roster
from deps import require_underduck

# stats는 매 요청마다 원천 데이터에서 집계한다(시트 폐기 대비).
#   - apps/goals/assists: matches 행의 명단(쉼표 결합 텍스트)에서 이름 등장 횟수
#   - mom: mom_vote를 (경기 × vote_type[공격/수비])별 최다득표로 집계
# (구버전: 시트 수식 산출물을 stats 테이블에 스냅샷해 읽기만 했음 → 폐기)
router = APIRouter(
    prefix="/api/underduck/stats",
    tags=["stats"],
    dependencies=[Depends(require_underduck)],
)


def _names(csv: str | None) -> list[str]:
    """쉼표로 이어붙인 명단 → 공백/빈 슬롯 제거한 이름 리스트."""
    if not csv:
        return []
    return [n.strip() for n in csv.split(",") if n and n.strip()]


@router.get("", response_model=list[schemas.StatOut])
def list_stats(db: Session = Depends(get_db)):
    apps: dict[str, int] = defaultdict(int)
    goals: dict[str, int] = defaultdict(int)
    assists: dict[str, int] = defaultdict(int)
    mom: dict[str, int] = defaultdict(int)

    # ── matches: 골/도움/출전 집계 ──
    for m in db.scalars(select(Match)):
        for name in _names(m.goals):
            goals[name] += 1
        for name in _names(m.assists):
            assists[name] += 1
        for name in set(_names(m.attendees)):  # 한 경기당 출전 1회
            apps[name] += 1

    # ── mom_vote: (경기, vote_type) 부문별 최다득표자 = 그 부문 MOM ──
    # vote_type은 공격/수비로 나뉘어 부문별로 한 명씩 나온다. 동률이면 동률자 모두 1회 인정.
    tally: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for v in db.scalars(select(MomVote)):
        if v.match_id is None or not v.voted_for:
            continue
        key = (v.match_id, (v.vote_type or "").strip())
        tally[key][v.voted_for.strip()] += 1
    for counts in tally.values():
        top = max(counts.values())
        for name, c in counts.items():
            if c == top:
                mom[name] += 1

    # ── 선수 명부: roster 우선(no/pos 채움) + 명단에만 등장하는 이름 뒤에 추가 ──
    seen: set[str] = set()
    rows: list[schemas.StatOut] = []
    idx = 0
    for r in db.scalars(select(Roster).order_by(Roster.id)):
        name = (r.name or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        idx += 1
        rows.append(schemas.StatOut(
            id=idx, no=r.no, name=name, pos=r.pos,
            apps=apps.get(name, 0), goals=goals.get(name, 0),
            assists=assists.get(name, 0), mom=mom.get(name, 0),
        ))

    extras = (set(apps) | set(goals) | set(assists) | set(mom)) - seen
    for name in sorted(extras):
        idx += 1
        rows.append(schemas.StatOut(
            id=idx, no=None, name=name, pos=None,
            apps=apps.get(name, 0), goals=goals.get(name, 0),
            assists=assists.get(name, 0), mom=mom.get(name, 0),
        ))

    return rows
