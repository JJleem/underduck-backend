from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import GalleryComment, GalleryLike
from deps import Caller, assert_owner_or_admin, caller, effective_kakao_id, require_underduck
from naming import resolve_name

router = APIRouter(prefix="/api/underduck/gallery", tags=["gallery"], dependencies=[Depends(require_underduck)])


@router.post("/state", response_model=list[schemas.GalleryStateOut])
def state(body: schemas.GalleryStateRequest, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    uid = effective_kakao_id(c, body.kakao_id)
    likes = dict(db.execute(select(GalleryLike.artwork_id, func.count(GalleryLike.id)).group_by(GalleryLike.artwork_id)).all())
    comments = dict(db.execute(select(GalleryComment.artwork_id, func.count(GalleryComment.id)).group_by(GalleryComment.artwork_id)).all())
    mine = set(db.scalars(select(GalleryLike.artwork_id).where(GalleryLike.kakao_id == uid)).all())
    ids = set(likes) | set(comments) | mine
    return [{"artwork_id": i, "liked": i in mine, "like_count": likes.get(i, 0), "comment_count": comments.get(i, 0)} for i in ids]


@router.post("/{artwork_id}/like", response_model=schemas.GalleryLikeOut)
def toggle_like(artwork_id: str, body: schemas.GalleryStateRequest, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    uid = effective_kakao_id(c, body.kakao_id)
    row = db.scalar(select(GalleryLike).where(GalleryLike.artwork_id == artwork_id, GalleryLike.kakao_id == uid))
    if row:
        db.delete(row); liked = False
    else:
        db.add(GalleryLike(artwork_id=artwork_id, kakao_id=uid, created_at=datetime.now(timezone.utc))); liked = True
    db.commit()
    count = db.scalar(select(func.count(GalleryLike.id)).where(GalleryLike.artwork_id == artwork_id)) or 0
    return {"liked": liked, "like_count": count}


@router.get("/{artwork_id}/comments", response_model=list[schemas.GalleryCommentOut])
def list_comments(artwork_id: str, db: Session = Depends(get_db)):
    return db.scalars(select(GalleryComment).where(GalleryComment.artwork_id == artwork_id).order_by(GalleryComment.id)).all()


@router.post("/{artwork_id}/comments", response_model=schemas.GalleryCommentOut, status_code=201)
def create_comment(artwork_id: str, body: schemas.GalleryCommentCreate, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    row = GalleryComment(artwork_id=artwork_id, kakao_id=effective_kakao_id(c, body.kakao_id), author=resolve_name(db, body.author.strip()), message=body.message.strip(), created_at=datetime.now(timezone.utc))
    db.add(row); db.commit(); db.refresh(row)
    return row


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    row = db.get(GalleryComment, comment_id)
    if row is None: raise HTTPException(status_code=404, detail="comment not found")
    assert_owner_or_admin(c, row.kakao_id)
    db.delete(row); db.commit()
    return {"deleted": 1}
