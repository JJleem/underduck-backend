from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import NameAlias
from deps import require_underduck

router = APIRouter(
    prefix="/api/underduck/name-alias",
    tags=["name_alias"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.NameAliasOut])
def list_aliases(db: Session = Depends(get_db)):
    return db.scalars(select(NameAlias).order_by(NameAlias.kakao_name)).all()


@router.put("", response_model=schemas.NameAliasOut)
def upsert_alias(body: schemas.NameAliasUpsert, db: Session = Depends(get_db)):
    # kakao_name(카카오 닉네임) 기준 upsert
    key = body.kakao_name.strip()
    row = db.get(NameAlias, key)
    if row is None:
        row = NameAlias(kakao_name=key)
        db.add(row)
    row.real_name = body.real_name.strip()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{kakao_name}")
def delete_alias(kakao_name: str, db: Session = Depends(get_db)):
    row = db.get(NameAlias, kakao_name)
    if row is None:
        raise HTTPException(status_code=404, detail="alias not found")
    db.delete(row)
    db.commit()
    return {"deleted": 1}
