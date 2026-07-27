from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import User
from deps import Caller, caller, effective_kakao_id, require_underduck
from security import pseudonymize

router = APIRouter(
    prefix="/api/underduck/users",
    tags=["users"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.kakao_id)).all()


@router.get("/resolve", response_model=schemas.PseudonymOut)
def resolve_pseudonym(kakao_id: str):
    """카카오 원본 ID → 가명 ID(pid). DB를 건드리지 않는 순수 변환.

    프론트가 기존 세션(원본 ID를 담고 있음)을 pid로 갈아끼울 때 쓴다.
    (`/{kakao_id}` 보다 먼저 선언해 경로 매칭 충돌 회피.)
    """
    return {"kakao_id": pseudonymize(kakao_id)}


@router.get("/{kakao_id}", response_model=schemas.UserOut)
def get_user(kakao_id: str, db: Session = Depends(get_db)):
    u = db.get(User, pseudonymize(kakao_id))
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    return u


@router.post("", response_model=schemas.UserOut)
def upsert_user(
    body: schemas.UserUpsert,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    # 신원 헤더가 오면 그 값이 우선 → 남의 프로필 덮어쓰기 차단.
    # (최초 로그인 시점에는 아직 세션이 없어 헤더가 없다 → 본문 값 사용.)
    kakao_id = effective_kakao_id(c, body.kakao_id)
    now = datetime.now(timezone.utc)
    u = db.get(User, kakao_id)
    if u is None:
        u = User(kakao_id=kakao_id, joined_at=now)
        db.add(u)
    u.nickname = body.nickname
    u.profile_image = body.profile_image
    u.last_login = now
    db.commit()
    db.refresh(u)
    return u
