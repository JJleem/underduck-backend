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


@router.post("/resolve", response_model=schemas.PseudonymOut)
def resolve_pseudonym(body: schemas.PseudonymResolve):
    """카카오 원본 ID → 가명 ID(pid). DB를 건드리지 않는 순수 변환.

    프론트가 기존 세션(원본 ID를 담고 있음)을 pid로 갈아끼울 때 쓴다.

    **GET + 쿼리스트링이 아니라 POST + 본문인 이유**: nginx access log는 쿼리스트링을
    그대로 기록한다. GET으로 두면 로그인할 때마다 원본 카카오 ID가 서버 로그에 평문으로
    쌓여, DB에서 없앤 의미가 사라진다. 본문은 로그에 남지 않는다.

    (`/{kakao_id}` 보다 먼저 선언해 경로 매칭 충돌 회피.)
    """
    return {"kakao_id": pseudonymize(body.kakao_id)}


@router.get("/{kakao_id}", response_model=schemas.UserOut)
def get_user(kakao_id: str, db: Session = Depends(get_db)):
    # 같은 이유로 경로에 원본 ID를 넣어 부르지 말 것 — 로그에 남는다. pid로 부르면 된다.
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
