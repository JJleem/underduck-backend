from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Match
from deps import require_underduck

router = APIRouter(
    prefix="/api/underduck/matches",
    tags=["matches"],
    dependencies=[Depends(require_underduck)],
)

MAX_PHOTOS = 5


def _get_or_404(db: Session, match_id: int) -> Match:
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="match not found")
    return m


@router.get("", response_model=list[schemas.MatchOut])
def list_matches(db: Session = Depends(get_db)):
    return db.scalars(select(Match).order_by(Match.match_id)).all()


@router.get("/{match_id}", response_model=schemas.MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, match_id)


@router.post("", response_model=schemas.MatchOut, status_code=201)
def create_match(body: schemas.MatchCreate, db: Session = Depends(get_db)):
    next_id = (db.scalar(select(func.max(Match.match_id))) or -1) + 1
    m = Match(
        match_id=next_id,
        date=body.date,
        time=body.time,
        location=body.location,
        opponent=body.opponent,
        type=body.type,
        result="예정",
        weather=body.weather,
        attendance_status="진행중",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.patch("/{match_id}", response_model=schemas.MatchOut)
def patch_match(match_id: int, body: schemas.MatchPatch, db: Session = Depends(get_db)):
    m = _get_or_404(db, match_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return m


@router.post("/{match_id}/photos", response_model=schemas.MatchOut)
def add_photos(match_id: int, body: schemas.PhotoAdd, db: Session = Depends(get_db)):
    m = _get_or_404(db, match_id)
    current = [u for u in (m.photos.split(",") if m.photos else []) if u]
    for u in body.urls:
        if u and u not in current:
            current.append(u)
    if len(current) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"최대 {MAX_PHOTOS}장")
    m.photos = ",".join(current)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{match_id}/photos", response_model=schemas.MatchOut)
def remove_photo(match_id: int, body: schemas.PhotoRemove, db: Session = Depends(get_db)):
    m = _get_or_404(db, match_id)
    current = [u for u in (m.photos.split(",") if m.photos else []) if u and u != body.url]
    m.photos = ",".join(current)
    db.commit()
    db.refresh(m)
    return m
