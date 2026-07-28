from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Lineup
from deps import require_admin, require_underduck

router = APIRouter(
    prefix="/api/underduck/lineup",
    tags=["lineup"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.LineupOut])
def list_lineup(match_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Lineup).order_by(Lineup.id)
    if match_id is not None:
        stmt = stmt.where(Lineup.match_id == match_id)
    return db.scalars(stmt).all()


@router.put("", dependencies=[Depends(require_admin)])
def upsert_lineup(body: schemas.LineupUpsert, db: Session = Depends(get_db)):
    players = [p for p in body.players if p]
    subs = [s for s in body.subs if s]
    is_empty = not players and not subs and not body.substitutions

    row = db.scalar(
        select(Lineup).where(Lineup.match_id == body.match_id, Lineup.quarter == body.quarter)
    )
    # 비어있으면 삭제(프론트 writeLineup 시맨틱)
    if is_empty:
        if row is not None:
            db.delete(row)
            db.commit()
        return {"deleted": row is not None}

    if row is None:
        row = Lineup(match_id=body.match_id, quarter=body.quarter)
        db.add(row)
    row.formation = body.formation
    row.players = body.players
    row.subs = body.subs
    row.substitutions = body.substitutions
    row.positions = body.positions
    row.tactic = body.tactic
    row.instructions = body.instructions
    db.commit()
    db.refresh(row)
    return schemas.LineupOut.model_validate(row)
