from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import VoteComment
from deps import require_underduck
from naming import resolve_name

router = APIRouter(
    prefix="/api/underduck/vote-comment",
    tags=["vote_comment"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.VoteCommentOut])
def list_comments(match_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(VoteComment).order_by(VoteComment.id)
    if match_id is not None:
        stmt = stmt.where(VoteComment.match_id == match_id)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.VoteCommentOut, status_code=201)
def create_comment(body: schemas.VoteCommentCreate, db: Session = Depends(get_db)):
    c = VoteComment(
        match_id=body.match_id,
        kakao_id=body.kakao_id,
        nickname=resolve_name(db, body.nickname.strip()),
        message=body.message.strip(),
        timestamp=datetime.now(timezone.utc),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    c = db.get(VoteComment, comment_id)
    if c is None:
        raise HTTPException(status_code=404, detail="comment not found")
    db.delete(c)
    db.commit()
    return {"deleted": 1}
