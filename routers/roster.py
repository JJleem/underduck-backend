from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Roster
from deps import require_underduck

router = APIRouter(
    prefix="/api/underduck/roster",
    tags=["roster"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.RosterOut])
def list_roster(db: Session = Depends(get_db)):
    return db.scalars(select(Roster).order_by(Roster.id)).all()


@router.post("", response_model=schemas.RosterOut, status_code=201)
def create_roster(body: schemas.RosterCreate, db: Session = Depends(get_db)):
    r = Roster(no=body.no, name=body.name, pos=body.pos, status=body.status)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r
