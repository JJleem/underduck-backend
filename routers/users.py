from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import User
from deps import require_underduck

router = APIRouter(
    prefix="/api/underduck/users",
    tags=["users"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.kakao_id)).all()


@router.get("/{kakao_id}", response_model=schemas.UserOut)
def get_user(kakao_id: str, db: Session = Depends(get_db)):
    u = db.get(User, kakao_id)
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    return u


@router.post("", response_model=schemas.UserOut)
def upsert_user(body: schemas.UserUpsert, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    u = db.get(User, body.kakao_id)
    if u is None:
        u = User(kakao_id=body.kakao_id, joined_at=now)
        db.add(u)
    u.nickname = body.nickname
    u.profile_image = body.profile_image
    u.last_login = now
    db.commit()
    db.refresh(u)
    return u
