from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import MomVote
from deps import Caller, caller, require_underduck
from naming import effective_name, resolve_name

router = APIRouter(
    prefix="/api/underduck/mom-vote",
    tags=["mom_vote"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.MomVoteOut])
def list_mom_votes(match_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(MomVote).order_by(MomVote.id)
    if match_id is not None:
        stmt = stmt.where(MomVote.match_id == match_id)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.MomVoteOut, status_code=201)
def create_mom_vote(
    body: schemas.MomVoteCreate,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    # (경기, 투표자, 부문) 당 1표. 같은 조합이 이미 있으면 갈아끼운다.
    #
    # 프론트는 이미 DELETE → POST 순으로 부르고 있어 사용자 입장에서는 동작이 같다.
    # 하지만 HTTP 2번으로 쪼개져 있어 경합이나 API 직접 호출로 표를 무한히 쌓을 수 있었다.
    # UNIQUE 제약으로 막으면 그 순간 사용자에게 500이 보이므로, 여기서 흡수한다.
    voter = effective_name(c, db, resolve_name(db, body.voter_name.strip()))
    vote_type = body.vote_type.strip()
    for stale in db.scalars(
        select(MomVote).where(
            MomVote.match_id == body.match_id,
            MomVote.voter_name == voter,
            MomVote.vote_type == vote_type,
        )
    ).all():
        db.delete(stale)

    v = MomVote(
        match_id=body.match_id,
        voter_name=voter,
        voted_for=resolve_name(db, body.voted_for.strip()),
        vote_type=vote_type,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.delete("")
def delete_mom_vote(
    body: schemas.MomVoteDelete,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    # 자기 투표만 삭제 가능(신원 헤더가 있을 때).
    stmt = select(MomVote).where(
        MomVote.match_id == body.match_id,
        MomVote.voter_name == effective_name(c, db, resolve_name(db, body.voter_name)),
    )
    if body.vote_type is not None:
        stmt = stmt.where(MomVote.vote_type == body.vote_type)
    rows = db.scalars(stmt).all()
    for r in rows:
        db.delete(r)
    db.commit()
    return {"deleted": len(rows)}
