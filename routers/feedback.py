from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Feedback
from deps import Caller, caller, require_underduck
from naming import effective_name, owned_name, resolve_name

router = APIRouter(
    prefix="/api/underduck/feedback",
    tags=["feedback"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.FeedbackOut])
def list_feedback(match_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Feedback).order_by(Feedback.id)
    if match_id is not None:
        stmt = stmt.where(Feedback.match_id == match_id)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.FeedbackOut, status_code=201)
def create_feedback(
    body: schemas.FeedbackCreate,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    f = Feedback(
        match_id=body.match_id,
        name=effective_name(c, db, resolve_name(db, body.name.strip())),
        message=body.message.strip(),
        timestamp=datetime.now(timezone.utc),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{feedback_id}")
def delete_feedback(
    feedback_id: int,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    f = db.get(Feedback, feedback_id)
    if f is None:
        raise HTTPException(status_code=404, detail="feedback not found")
    owner = owned_name(c, db, resolve_name(db, (f.name or "").strip()))
    if c.is_identified and not c.is_admin and owner != resolve_name(db, (f.name or "").strip()):
        raise HTTPException(status_code=403, detail="Forbidden: not the author")
    db.delete(f)
    db.commit()
    return {"deleted": 1}
