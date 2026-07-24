from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import BoardComment, BoardPost
from deps import require_underduck
from naming import resolve_name

router = APIRouter(
    prefix="/api/underduck/board",
    tags=["board"],
    dependencies=[Depends(require_underduck)],
)


# ── posts ──
@router.get("", response_model=list[schemas.BoardPostOut])
def list_posts(db: Session = Depends(get_db)):
    # 최신순 + 각 글의 댓글 수 동봉.
    counts = dict(
        db.execute(
            select(BoardComment.post_id, func.count(BoardComment.id)).group_by(BoardComment.post_id)
        ).all()
    )
    posts = db.scalars(select(BoardPost).order_by(BoardPost.id.desc())).all()
    out = []
    for p in posts:
        item = schemas.BoardPostOut.model_validate(p)
        item.comment_count = counts.get(p.id, 0)
        out.append(item)
    return out


@router.get("/{post_id}", response_model=schemas.BoardPostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    p = db.get(BoardPost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")
    item = schemas.BoardPostOut.model_validate(p)
    item.comment_count = db.scalar(
        select(func.count(BoardComment.id)).where(BoardComment.post_id == post_id)
    )
    return item


@router.post("", response_model=schemas.BoardPostOut, status_code=201)
def create_post(body: schemas.BoardPostCreate, db: Session = Depends(get_db)):
    p = BoardPost(
        kakao_id=body.kakao_id,
        author=resolve_name(db, body.author.strip()),
        title=body.title.strip(),
        youtube_url=body.youtube_url.strip(),
        body=(body.body or "").strip() or None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    p = db.get(BoardPost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")
    # 글 삭제 시 딸린 댓글도 함께 제거.
    db.query(BoardComment).filter(BoardComment.post_id == post_id).delete()
    db.delete(p)
    db.commit()
    return {"deleted": 1}


# ── comments ──
@router.get("/{post_id}/comments", response_model=list[schemas.BoardCommentOut])
def list_comments(post_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(BoardComment).where(BoardComment.post_id == post_id).order_by(BoardComment.id)
    ).all()


@router.post("/{post_id}/comments", response_model=schemas.BoardCommentOut, status_code=201)
def create_comment(post_id: int, body: schemas.BoardCommentCreate, db: Session = Depends(get_db)):
    if db.get(BoardPost, post_id) is None:
        raise HTTPException(status_code=404, detail="post not found")
    c = BoardComment(
        post_id=post_id,
        kakao_id=body.kakao_id,
        author=resolve_name(db, body.author.strip()),
        message=body.message.strip(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    c = db.get(BoardComment, comment_id)
    if c is None:
        raise HTTPException(status_code=404, detail="comment not found")
    db.delete(c)
    db.commit()
    return {"deleted": 1}
