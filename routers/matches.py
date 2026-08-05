from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Match, MatchLike
from deps import Caller, caller, effective_kakao_id, require_admin, require_underduck
from security import pseudonymize

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


def _out(db: Session, m: Match) -> schemas.MatchOut:
    """단건 응답. like_count 를 채우지 않으면 기본값 0이 나가서, 수정 직후
    화면의 좋아요 수가 0으로 되돌아간 것처럼 보인다."""
    item = schemas.MatchOut.model_validate(m)
    item.like_count = db.scalar(
        select(func.count(MatchLike.id)).where(MatchLike.match_id == m.match_id)
    ) or 0
    return item


@router.get("", response_model=list[schemas.MatchOut])
def list_matches(db: Session = Depends(get_db)):
    # 좋아요 수는 한 번의 group by 로 모아 붙인다 (경기 수만큼 왕복하지 않게).
    like_counts = dict(
        db.execute(
            select(MatchLike.match_id, func.count(MatchLike.id)).group_by(MatchLike.match_id)
        ).all()
    )
    out = []
    for m in db.scalars(select(Match).order_by(Match.match_id)).all():
        item = schemas.MatchOut.model_validate(m)
        item.like_count = like_counts.get(m.match_id, 0)
        out.append(item)
    return out


@router.get("/my-likes", response_model=list[int])
def my_likes(kakao_id: str, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    # 내가 좋아요한 match_id 목록. (`/{match_id}` 보다 먼저 선언해 경로 매칭 충돌 회피)
    # 신원 헤더가 오면 남의 목록을 조회하지 못하도록 세션 사용자로 강제한다.
    target = effective_kakao_id(c, pseudonymize(kakao_id))
    rows = db.scalars(select(MatchLike.match_id).where(MatchLike.kakao_id == target)).all()
    return [r for r in rows if r is not None]


@router.get("/{match_id}", response_model=schemas.MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    return _out(db, _get_or_404(db, match_id))


@router.post("/{match_id}/like", response_model=schemas.MatchLikeOut)
def toggle_like(
    match_id: int,
    body: schemas.MatchLikeToggle,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    _get_or_404(db, match_id)
    kakao_id = effective_kakao_id(c, body.kakao_id)
    existing = db.scalars(
        select(MatchLike).where(MatchLike.match_id == match_id, MatchLike.kakao_id == kakao_id)
    ).first()
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(
            MatchLike(
                match_id=match_id,
                kakao_id=kakao_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        liked = True
    db.commit()
    count = db.scalar(select(func.count(MatchLike.id)).where(MatchLike.match_id == match_id))
    return {"liked": liked, "like_count": count or 0}


@router.post("", response_model=schemas.MatchOut, status_code=201, dependencies=[Depends(require_admin)])
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
    return _out(db, m)


@router.patch("/{match_id}", response_model=schemas.MatchOut, dependencies=[Depends(require_admin)])
def patch_match(match_id: int, body: schemas.MatchPatch, db: Session = Depends(get_db)):
    m = _get_or_404(db, match_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return _out(db, m)


@router.post("/{match_id}/photos", response_model=schemas.MatchOut, dependencies=[Depends(require_admin)])
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
    return _out(db, m)


@router.delete("/{match_id}/photos", response_model=schemas.MatchOut, dependencies=[Depends(require_admin)])
def remove_photo(match_id: int, body: schemas.PhotoRemove, db: Session = Depends(get_db)):
    m = _get_or_404(db, match_id)
    current = [u for u in (m.photos.split(",") if m.photos else []) if u and u != body.url]
    m.photos = ",".join(current)
    db.commit()
    db.refresh(m)
    return _out(db, m)
