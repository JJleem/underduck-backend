"""시즌 경계.

시즌은 컬럼이 아니라 **경기 날짜에서 파생**된다. matches.date(YYYY-MM-DD)가 어느
구간에 들어가느냐로 정해지므로 마이그레이션도 백필도 없다. 아래 SEASONS 에 한 줄
더 넣는 것이 전부다.

⚠️ 프론트에 같은 표가 있다(underducfc-dashboard/app/lib/seasons.ts).
   스탯 집계는 여기서 하고 전적·프로필 집계는 프론트에서 하므로, 둘이 어긋나면
   순위 페이지와 프로필이 다른 말을 한다. **고칠 땐 반드시 같이 고친다.**
   (id 목록이 어긋나면 list_stats 가 400 으로 즉시 터지도록 해 뒀다)
"""
import re

# start 오름차순으로만 넣는다 — season_of 가 뒤에서부터 훑는다.
# start=None 은 "시작 경계 없음" = 이 시즌보다 오래된 경기도 전부 이 시즌.
# 첫 시즌에만 쓴다. 그래야 옛 경기가 어느 시즌에도 안 속해 기록에서 사라지지 않는다.
SEASONS: list[dict[str, str | None]] = [
    {"id": "2526", "label": "25-26", "start": None},
    # 확정 — 26-27 개막 2026-11-01 (25-26 마지막 경기는 2026-10-31).
    # 프론트 seasons.ts 와 **같은 값**이어야 한다. 어긋나면 list_stats 가 400 을 던진다.
    {"id": "2627", "label": "26-27", "start": "2026-11-01"},
]

SEASON_IDS = frozenset(s["id"] for s in SEASONS)

_DATE_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")


def normalize_date(raw: str | None) -> str:
    """느슨한 날짜 문자열 → "YYYY-MM-DD". 못 읽으면 "".

    시트에서 넘어온 옛 데이터에 "2025-8-3" 같은 표기가 섞여 있다.
    """
    m = _DATE_RE.match((raw or "").strip())
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def season_of(date: str | None) -> str | None:
    """경기 날짜가 속한 시즌 id. 날짜를 못 읽으면 None(어느 시즌에도 안 든다)."""
    d = normalize_date(date)
    if not d:
        return None
    for s in reversed(SEASONS):
        start = s["start"]
        if start is None or d >= start:
            return s["id"]
    return None


def is_in_season(date: str | None, season_id: str) -> bool:
    return season_of(date) == season_id
