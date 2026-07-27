from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Roster
from deps import Caller, caller, require_admin, require_underduck
from naming import effective_name, resolve_name

router = APIRouter(
    prefix="/api/underduck/roster",
    tags=["roster"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.RosterOut])
def list_roster(db: Session = Depends(get_db)):
    return db.scalars(select(Roster).order_by(Roster.id)).all()


@router.put("/pref-pos", response_model=schemas.RosterOut)
def update_pref_pos(
    body: schemas.RosterPrefPosUpdate,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    # 본인 이름(실명 정규화)으로 로스터 행을 찾아 선호 포지션만 갱신.
    # 신원 헤더가 오면 세션 사용자의 실명으로 강제 → 남의 선호 포지션 변경 차단.
    # (경로 파라미터 /{roster_id} 보다 먼저 선언해야 매칭 충돌이 없다.)
    name = effective_name(c, db, resolve_name(db, body.name.strip()))
    r = db.scalars(select(Roster).where(Roster.name == name)).first()
    if r is None:
        raise HTTPException(status_code=404, detail="roster not found for name")
    r.pref_pos = body.pref_pos.strip()
    db.commit()
    db.refresh(r)
    return r


@router.post("", response_model=schemas.RosterOut, status_code=201, dependencies=[Depends(require_admin)])
def create_roster(body: schemas.RosterCreate, db: Session = Depends(get_db)):
    r = Roster(no=body.no, name=body.name, pos=body.pos, status=body.status)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.put("/{roster_id}", response_model=schemas.RosterOut, dependencies=[Depends(require_admin)])
def update_roster(roster_id: int, body: schemas.RosterCreate, db: Session = Depends(get_db)):
    # roster_id 행만 no/name/pos/status 갱신 (memo는 미전송이므로 기존 값 유지)
    r = db.get(Roster, roster_id)
    if r is None:
        raise HTTPException(status_code=404, detail="roster not found")
    r.no, r.name, r.pos, r.status = body.no, body.name, body.pos, body.status
    db.commit()
    db.refresh(r)
    return r
