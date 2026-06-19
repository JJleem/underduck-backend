"""Google Sheets → underduck Postgres 일회성 이전 스크립트 (재실행 안전: 테이블 비우고 다시 적재).

필요 환경변수:
  UNDERDUCK_DATABASE_URL   (db.connection 이 사용)
  GOOGLE_SHEET_ID
  GOOGLE_SHEETS_API_KEY    (읽기 전용 공개 키)

실행:
  cd underduck-backend
  GOOGLE_SHEET_ID=... GOOGLE_SHEETS_API_KEY=... .venv/bin/python -m scripts.import_sheets
"""
import os
import sys
import time
from datetime import datetime

import httpx

from db.connection import SessionLocal
from db import models

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
API_KEY = os.environ.get("GOOGLE_SHEETS_API_KEY", "")


def _fetch(sheet: str, retries: int = 5) -> list[list[str]]:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{sheet}"
    for attempt in range(retries):
        r = httpx.get(url, params={"key": API_KEY, "majorDimension": "ROWS"}, timeout=30)
        if r.status_code == 429 and attempt < retries - 1:
            wait = 2 ** attempt
            print(f"  {sheet}: 429, {wait}s 후 재시도...", file=sys.stderr)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json().get("values", [])
    return []


def _cell(row: list[str], i: int) -> str | None:
    v = row[i].strip() if i < len(row) and row[i] is not None else ""
    return v or None


def _int(row: list[str], i: int) -> int | None:
    v = _cell(row, i)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _ts(row: list[str], i: int):
    v = _cell(row, i)
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> int:
    if not SHEET_ID or not API_KEY:
        print("ERROR: GOOGLE_SHEET_ID / GOOGLE_SHEETS_API_KEY 필요", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        # 재실행 안전: 대상 테이블 전부 비우기
        for m in (models.MomVote, models.VoteComment, models.AttendanceVote,
                  models.Featured, models.PushSubscription):
            db.query(m).delete()
        db.commit()

        counts: dict[str, int] = {}

        # mom_vote: matchId, voterName, votedFor, voteType, timestamp
        rows = _fetch("mom_vote")[1:]
        objs = [models.MomVote(match_id=_int(r, 0), voter_name=_cell(r, 1),
                               voted_for=_cell(r, 2), vote_type=_cell(r, 3), timestamp=_ts(r, 4))
                for r in rows if any(c.strip() for c in r)]
        db.add_all(objs); counts["mom_vote"] = len(objs)

        # vote_comment: matchId, kakaoId, nickname, message, timestamp
        rows = _fetch("vote_comment")[1:]
        objs = [models.VoteComment(match_id=_int(r, 0), kakao_id=_cell(r, 1),
                                   nickname=_cell(r, 2), message=_cell(r, 3), timestamp=_ts(r, 4))
                for r in rows if any(c.strip() for c in r)]
        db.add_all(objs); counts["vote_comment"] = len(objs)

        # attendance_vote: matchId, kakaoId, nickname, response, timestamp
        rows = _fetch("attendance_vote")[1:]
        objs = [models.AttendanceVote(match_id=_int(r, 0), kakao_id=_cell(r, 1),
                                      nickname=_cell(r, 2), response=_cell(r, 3), timestamp=_ts(r, 4))
                for r in rows if any(c.strip() for c in r)]
        db.add_all(objs); counts["attendance_vote"] = len(objs)

        # featured: 선수명, 칭호id1~3
        rows = _fetch("featured")[1:]
        objs = [models.Featured(player_name=_cell(r, 0), title_id1=_cell(r, 1),
                                title_id2=_cell(r, 2), title_id3=_cell(r, 3))
                for r in rows if _cell(r, 0)]
        db.add_all(objs); counts["featured"] = len(objs)

        # push_subscriptions: endpoint, p256dh, auth
        rows = _fetch("push_subscriptions")[1:]
        seen: set[str] = set()
        objs = []
        for r in rows:
            ep = _cell(r, 0)
            if not ep or ep in seen:
                continue
            seen.add(ep)
            objs.append(models.PushSubscription(endpoint=ep, p256dh=_cell(r, 1), auth=_cell(r, 2)))
        db.add_all(objs); counts["push_subscription"] = len(objs)

        db.commit()
        print("이전 완료:", counts)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
