from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import AttendanceVote, Match
from deps import require_underduck

router = APIRouter(
    prefix="/api/underduck/attendance",
    tags=["attendance"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.AttendanceOut])
def list_attendance(match_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(AttendanceVote).order_by(AttendanceVote.id)
    if match_id is not None:
        stmt = stmt.where(AttendanceVote.match_id == match_id)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.AttendanceOut)
def upsert_attendance(body: schemas.AttendanceUpsert, db: Session = Depends(get_db)):
    # (match_id, kakao_id) 기준 upsert
    row = db.scalar(
        select(AttendanceVote).where(
            AttendanceVote.match_id == body.match_id,
            AttendanceVote.kakao_id == body.kakao_id,
        )
    )
    if row is None:
        row = AttendanceVote(match_id=body.match_id, kakao_id=body.kakao_id)
        db.add(row)
    row.nickname = body.nickname.strip()
    row.response = body.response
    row.timestamp = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{match_id}/finalize")
def finalize_attendance(match_id: int, db: Session = Depends(get_db)):
    # "참석" 응답자 닉네임을 모아 matches.attendees(L) + attendance_status="마감" 기록
    rows = db.scalars(
        select(AttendanceVote).where(
            AttendanceVote.match_id == match_id, AttendanceVote.response == "참석"
        )
    ).all()
    attendees = ",".join(r.nickname.strip() for r in rows if r.nickname)
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="match not found")
    m.attendees = attendees
    m.attendance_status = "마감"
    db.commit()
    return {"attendees": attendees}


@router.patch("/{match_id}/status")
def set_status(match_id: int, body: schemas.AttendanceStatus, db: Session = Depends(get_db)):
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="match not found")
    m.attendance_status = body.status
    db.commit()
    return {"match_id": match_id, "attendance_status": body.status}
