from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import PushSubscription
from deps import require_underduck

router = APIRouter(
    prefix="/api/underduck/push",
    tags=["push"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.PushOut])
def list_subscriptions(db: Session = Depends(get_db)):
    return db.scalars(select(PushSubscription).order_by(PushSubscription.id)).all()


@router.post("", response_model=schemas.PushOut)
def add_subscription(body: schemas.PushCreate, db: Session = Depends(get_db)):
    # endpoint 기준 upsert (중복 구독 방지)
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if row is None:
        row = PushSubscription(endpoint=body.endpoint)
        db.add(row)
    row.p256dh = body.p256dh
    row.auth = body.auth
    db.commit()
    db.refresh(row)
    return row


@router.delete("")
def remove_subscription(body: schemas.PushDelete, db: Session = Depends(get_db)):
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if row is None:
        return {"deleted": 0}
    db.delete(row)
    db.commit()
    return {"deleted": 1}
