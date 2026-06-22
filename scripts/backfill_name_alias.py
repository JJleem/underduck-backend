"""기존 DB 행의 카카오 닉네임을 name_alias 기준 실명으로 일괄 변환 (일회성, 재실행 안전).

대상:
  mom_vote.voter_name / voted_for
  vote_comment.nickname
  attendance_vote.nickname
  feedback.name
  matches.mom (단일) / attendees (콤마 구분 CSV)

실행:
  cd underduck-backend
  .venv/bin/python -m scripts.backfill_name_alias          # 적용
  .venv/bin/python -m scripts.backfill_name_alias --dry    # 미적용(영향 행만 출력)
"""
import sys

from sqlalchemy import select

from db.connection import SessionLocal
from db import models
from naming import resolve_name


def _csv(db, v: str | None) -> str | None:
    if not v:
        return v
    return ",".join(resolve_name(db, t.strip()) or t for t in v.split(","))


def main() -> int:
    dry = "--dry" in sys.argv
    db = SessionLocal()
    changed: dict[str, int] = {}
    try:
        def bump(key):
            changed[key] = changed.get(key, 0) + 1

        for v in db.scalars(select(models.MomVote)).all():
            new_voter, new_voted = resolve_name(db, v.voter_name), resolve_name(db, v.voted_for)
            if new_voter != v.voter_name or new_voted != v.voted_for:
                v.voter_name, v.voted_for = new_voter, new_voted
                bump("mom_vote")

        for c in db.scalars(select(models.VoteComment)).all():
            n = resolve_name(db, c.nickname)
            if n != c.nickname:
                c.nickname = n
                bump("vote_comment")

        for a in db.scalars(select(models.AttendanceVote)).all():
            n = resolve_name(db, a.nickname)
            if n != a.nickname:
                a.nickname = n
                bump("attendance_vote")

        for f in db.scalars(select(models.Feedback)).all():
            n = resolve_name(db, f.name)
            if n != f.name:
                f.name = n
                bump("feedback")

        for m in db.scalars(select(models.Match)).all():
            new_mom, new_att = resolve_name(db, m.mom), _csv(db, m.attendees)
            if new_mom != m.mom or new_att != m.attendees:
                m.mom, m.attendees = new_mom, new_att
                bump("matches")

        if dry:
            db.rollback()
            print("[dry] 변경 예정 행:", changed or "없음")
        else:
            db.commit()
            print("변경 완료 행:", changed or "없음")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
