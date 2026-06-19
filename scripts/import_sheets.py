"""Google Sheets → underduck Postgres 일회성 이전 스크립트 (재실행 안전: 테이블 비우고 다시 적재).

필요 환경변수:
  UNDERDUCK_DATABASE_URL   (db.connection 이 사용)
  GOOGLE_SHEET_ID
  GOOGLE_SHEETS_API_KEY    (읽기 전용 공개 키)

실행:
  cd underduck-backend
  GOOGLE_SHEET_ID=... GOOGLE_SHEETS_API_KEY=... .venv/bin/python -m scripts.import_sheets
"""
import json
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
                  models.Featured, models.PushSubscription, models.Match,
                  models.Roster, models.Stat, models.Notice, models.Lineup,
                  models.Feedback, models.User, models.Media):
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

        # matches: A~O. match_id = 데이터행 0-based 인덱스(보존). CSV 필드는 원형 유지.
        rows = _fetch("matches")[1:]
        objs = [models.Match(
            match_id=i, date=_cell(r, 0), time=_cell(r, 1), location=_cell(r, 2),
            opponent=_cell(r, 3), our_score=_int(r, 4), their_score=_int(r, 5),
            result=_cell(r, 6), type=_cell(r, 7), goals=_cell(r, 8), assists=_cell(r, 9),
            mom=_cell(r, 10), attendees=_cell(r, 11), photos=_cell(r, 12),
            weather=_cell(r, 13), attendance_status=_cell(r, 14),
        ) for i, r in enumerate(rows)]
        db.add_all(objs); counts["matches"] = len(objs)

        # roster
        rows = _fetch("roster")[1:]
        objs = [models.Roster(no=_cell(r, 0), name=_cell(r, 1), pos=_cell(r, 2),
                              status=_cell(r, 3), memo=_cell(r, 5))
                for r in rows if any(c.strip() for c in r)]
        db.add_all(objs); counts["roster"] = len(objs)

        # stats (수식 스냅샷)
        rows = _fetch("stats")[1:]
        objs = [models.Stat(no=_cell(r, 0), name=_cell(r, 1), pos=_cell(r, 2),
                            apps=_int(r, 3), goals=_int(r, 4), assists=_int(r, 5), mom=_int(r, 6))
                for r in rows if any(c.strip() for c in r)]
        db.add_all(objs); counts["stats"] = len(objs)

        # notice: 활성 공지 1건(시트 row2 = 첫 데이터행)
        rows = _fetch("notice")[1:]
        n = 0
        if rows and any(c.strip() for c in rows[0]):
            r = rows[0]
            db.add(models.Notice(date=_cell(r, 0), title=_cell(r, 1), content=_cell(r, 2),
                                 important=(_cell(r, 3) == "Y"), location=_cell(r, 4)))
            n = 1
        counts["notice"] = n

        # lineup: p1~p11 → players[], sub1~sub5 → subs[], col T(19) → substitutions(JSON)
        rows = _fetch("lineup")[1:]
        objs = []
        for r in rows:
            if not any(c.strip() for c in r):
                continue
            players = [(_cell(r, 3 + i) or "") for i in range(11)]
            subs = [(_cell(r, 14 + i) or "") for i in range(5)]
            sub_raw = _cell(r, 19)
            try:
                substitutions = json.loads(sub_raw) if sub_raw else []
            except (ValueError, TypeError):
                substitutions = []
            objs.append(models.Lineup(match_id=_int(r, 0), quarter=_cell(r, 1),
                                      formation=_cell(r, 2), players=players, subs=subs,
                                      substitutions=substitutions))
        db.add_all(objs); counts["lineup"] = len(objs)

        # feedback: matchId, timestamp, name, message
        rows = _fetch("feedback")[1:]
        objs = [models.Feedback(match_id=_int(r, 0), timestamp=_ts(r, 1),
                               name=_cell(r, 2), message=_cell(r, 3))
                for r in rows if any(c.strip() for c in r)]
        db.add_all(objs); counts["feedback"] = len(objs)

        # users: kakaoId, nickname, profileImage, joinedAt, lastLogin
        rows = _fetch("users")[1:]
        seen = set()
        objs = []
        for r in rows:
            kid = _cell(r, 0)
            if not kid or kid in seen:
                continue
            seen.add(kid)
            objs.append(models.User(kakao_id=kid, nickname=_cell(r, 1), profile_image=_cell(r, 2),
                                    joined_at=_ts(r, 3), last_login=_ts(r, 4)))
        db.add_all(objs); counts["users"] = len(objs)

        # media: type, url, title, uploadedAt
        rows = _fetch("media")[1:]
        seen = set()
        objs = []
        for r in rows:
            url = _cell(r, 1)
            if not url or url in seen:
                continue
            seen.add(url)
            objs.append(models.Media(type=_cell(r, 0), url=url, title=_cell(r, 2),
                                     uploaded_at=_ts(r, 3)))
        db.add_all(objs); counts["media"] = len(objs)

        db.commit()
        print("이전 완료:", counts)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
