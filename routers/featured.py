from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Featured
from deps import Caller, caller, require_underduck
from naming import effective_name, resolve_name

router = APIRouter(
    prefix="/api/underduck/featured",
    tags=["featured"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.FeaturedOut])
def list_featured(db: Session = Depends(get_db)):
    return db.scalars(select(Featured).order_by(Featured.player_name)).all()


@router.put("", response_model=schemas.FeaturedOut)
def upsert_featured(
    body: schemas.FeaturedUpsert,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    # 일반 회원은 세션 사용자 실명으로 강제해 남의 대표 칭호 변경을 막는다.
    # 관리자는 기존처럼 요청한 선수의 칭호를 변경할 수 있다.
    name = effective_name(c, db, resolve_name(db, body.player_name.strip()))
    ids = (body.title_ids + ["", "", ""])[:3]
    row = db.get(Featured, name)
    if row is None:
        row = Featured(player_name=name)
        db.add(row)
    row.title_id1, row.title_id2, row.title_id3 = (ids[0] or None, ids[1] or None, ids[2] or None)
    db.commit()
    db.refresh(row)
    return row
