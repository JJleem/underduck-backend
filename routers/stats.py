from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Match, Roster
from deps import require_underduck

# stats는 매 요청마다 원천 데이터에서 집계한다(시트 폐기 대비).
#   - apps/goals/assists: matches 행의 명단(쉼표 결합 텍스트)에서 이름 등장 횟수
#   - mom: matches.mom(확정 기록)에서 집계
# (구버전: 시트 수식 산출물을 stats 테이블에 스냅샷해 읽기만 했음 → 폐기)
#
# ⚠️ mom 은 예전에 mom_vote(투표 테이블)에서 셌는데, 그러면 확정 기록과 어긋난다.
#    투표 기능이 생기기 전 경기들은 관리자가 MOM 을 직접 넣어서 투표 기록이 아예
#    없다. 실제로 5명이 안 맞았다(강창훈 0 vs 2, 김광민 0 vs 1, 김주성 0 vs 1,
#    김준수 3 vs 4, 안원진 2 vs 3). 화면 어디서나 보여 주는 값은 matches.mom 이므로
#    집계도 거기서 한다 — 그래야 "프로필엔 왕관 4개인데 스탯은 3" 이 다시 안 생긴다.
router = APIRouter(
    prefix="/api/underduck/stats",
    tags=["stats"],
    dependencies=[Depends(require_underduck)],
)


def _is_outing(match_type: str | None) -> bool:
    """야유회인가. 공백 표기가 섞여 있어 지우고 비교한다."""
    return (match_type or "").replace(" ", "") == "야유회"


def _names(csv: str | None) -> list[str]:
    """쉼표로 이어붙인 명단 → 공백/빈 슬롯 제거한 이름 리스트."""
    if not csv:
        return []
    return [n.strip() for n in csv.split(",") if n and n.strip()]


def _mom_names(raw: str | None) -> list[str]:
    """MOM 필드 → 수상자 이름들.

    구분자가 두 겹이다. `/` 는 공격 MOM / 수비 MOM 을 나누고, `,` 는 같은 부문의
    공동 수상을 나눈다. 실제 데이터에 "금상덕,김준수 / 안원진" 처럼 둘 다 섞여 있다.
    쉼표로만 자르면 `/` 로 묶인 사람을 통째로 놓친다.
    (프론트의 match-result.momNames 와 같은 규칙)
    """
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split("/"):
        out.extend(n.strip() for n in part.split(",") if n.strip())
    return out


@router.get("", response_model=list[schemas.StatOut])
def list_stats(db: Session = Depends(get_db)):
    apps: dict[str, int] = defaultdict(int)
    goals: dict[str, int] = defaultdict(int)
    assists: dict[str, int] = defaultdict(int)
    mom: dict[str, int] = defaultdict(int)

    # ── matches: 골/도움/출전 집계 ──
    for m in db.scalars(select(Match)):
        # 야유회는 경기가 아니라 행사다. 출전 수에 들어가면 안 되고, goals 칸에
        # 선수 이름 대신 종목이 적혀 있다("바베큐, 닭싸움, 족구, 피구, 실내").
        # 그래서 그대로 세면 그 다섯이 1골짜리 선수로 순위에 올라온다(실제로 올라와 있었다).
        # 자체전·풋살은 빼지 않는다 — 그건 실제로 공을 찬 경기다.
        if _is_outing(m.type):
            continue
        # 아직 안 치른 경기. 출석 투표나 관리자 사전 입력으로 명단이 미리 차 있어서
        # 그대로 세면 경기 전에 출전 수가 올라간다(8/8 자체전 명단 12명이 실제로
        # +1 씩 잡혀 있었다). 기록은 경기가 끝난 뒤에 생겨야 한다.
        if (m.result or "").strip() == "예정":
            continue
        for name in _names(m.goals):
            goals[name] += 1
        for name in _names(m.assists):
            assists[name] += 1
        for name in set(_names(m.attendees)):  # 한 경기당 출전 1회
            apps[name] += 1
        # 한 경기에서 같은 사람이 두 번 적혀도 1회로 센다.
        for name in set(_mom_names(m.mom)):
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
