from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import BoardComment, BoardLike, BoardPost, User
from deps import Caller, assert_owner_or_admin, caller, effective_kakao_id, require_underduck
from naming import resolve_name
from security import pseudonymize

router = APIRouter(
    prefix="/api/underduck/board",
    tags=["board"],
    dependencies=[Depends(require_underduck)],
)


# ── posts ──
@router.get("", response_model=list[schemas.BoardPostOut])
def list_posts(db: Session = Depends(get_db)):
    # 최신순 + 각 글의 댓글/좋아요 수 동봉.
    comment_counts = dict(
        db.execute(
            select(BoardComment.post_id, func.count(BoardComment.id)).group_by(BoardComment.post_id)
        ).all()
    )
    like_counts = dict(
        db.execute(
            select(BoardLike.post_id, func.count(BoardLike.id)).group_by(BoardLike.post_id)
        ).all()
    )
    # 수정된 글은 최신으로 올라온다 (수정 시각 우선, 없으면 작성 시각).
    posts = db.scalars(
        select(BoardPost).order_by(
            func.coalesce(BoardPost.updated_at, BoardPost.created_at).desc(),
            BoardPost.id.desc(),
        )
    ).all()
    out = []
    for p in posts:
        item = schemas.BoardPostOut.model_validate(p)
        item.comment_count = comment_counts.get(p.id, 0)
        item.like_count = like_counts.get(p.id, 0)
        out.append(item)
    return out


@router.get("/my-likes", response_model=list[int])
def my_likes(kakao_id: str, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    # 특정 사용자가 좋아요한 post_id 목록. (`/{post_id}` 보다 먼저 선언해 매칭 충돌 회피)
    # 신원 헤더가 오면 남의 목록을 조회하지 못하도록 세션 사용자로 강제한다.
    target = effective_kakao_id(c, pseudonymize(kakao_id))
    rows = db.scalars(select(BoardLike.post_id).where(BoardLike.kakao_id == target)).all()
    return [r for r in rows if r is not None]


@router.get("/like-givers", response_model=list[schemas.BoardLikeGiverOut])
def like_givers(db: Session = Depends(get_db)):
    # 누가 좋아요를 몇 번 눌렀는지 → kakao_id를 users.nickname → 실명 정규화로 집계.
    # (칭호 "좋아요 요정"용. `/{post_id}` 보다 먼저 선언.)
    counts = db.execute(
        select(BoardLike.kakao_id, func.count(BoardLike.id)).group_by(BoardLike.kakao_id)
    ).all()
    nick_by_id = {u.kakao_id: (u.nickname or "") for u in db.scalars(select(User)).all()}
    agg: dict[str, int] = {}
    for kakao_id, cnt in counts:
        nickname = nick_by_id.get(kakao_id, "")
        name = resolve_name(db, nickname.strip()) if nickname else ""
        if not name:
            continue
        agg[name] = agg.get(name, 0) + cnt
    return [{"name": k, "count": v} for k, v in agg.items()]


@router.get("/comments/all", response_model=list[schemas.BoardCommentOut])
def all_comments(db: Session = Depends(get_db)):
    # 전 게시글의 댓글 전체 (칭호 집계용). `/{post_id}` 보다 먼저 선언.
    return db.scalars(select(BoardComment).order_by(BoardComment.id)).all()


@router.get("/{post_id}", response_model=schemas.BoardPostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    p = db.get(BoardPost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")
    item = schemas.BoardPostOut.model_validate(p)
    item.comment_count = db.scalar(
        select(func.count(BoardComment.id)).where(BoardComment.post_id == post_id)
    )
    item.like_count = db.scalar(
        select(func.count(BoardLike.id)).where(BoardLike.post_id == post_id)
    )
    return item


@router.post("/{post_id}/like", response_model=schemas.BoardLikeOut)
def toggle_like(
    post_id: int,
    body: schemas.BoardLikeToggle,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    if db.get(BoardPost, post_id) is None:
        raise HTTPException(status_code=404, detail="post not found")
    kakao_id = effective_kakao_id(c, body.kakao_id)
    existing = db.scalars(
        select(BoardLike).where(BoardLike.post_id == post_id, BoardLike.kakao_id == kakao_id)
    ).first()
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(BoardLike(post_id=post_id, kakao_id=kakao_id, created_at=datetime.now(timezone.utc)))
        liked = True
    db.commit()
    count = db.scalar(select(func.count(BoardLike.id)).where(BoardLike.post_id == post_id))
    return {"liked": liked, "like_count": count or 0}


@router.post("", response_model=schemas.BoardPostOut, status_code=201)
def create_post(
    body: schemas.BoardPostCreate,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    kakao_id = effective_kakao_id(c, body.kakao_id)
    now = datetime.now(timezone.utc)

    # 전술 글은 1인 1개 — 이미 있으면 새로 만들지 않고 그 글을 수정한다.
    if body.lineup is not None:
        existing = db.scalar(
            select(BoardPost)
            .where(BoardPost.kakao_id == kakao_id, BoardPost.lineup.is_not(None))
            .order_by(BoardPost.id.desc())
        )
        if existing is not None:
            existing.title = body.title.strip()
            existing.body = (body.body or "").strip() or None
            existing.lineup = body.lineup.model_dump()
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return existing

    p = BoardPost(
        kakao_id=kakao_id,
        author=resolve_name(db, body.author.strip()),
        title=body.title.strip(),
        youtube_url=(body.youtube_url or "").strip() or None,
        body=(body.body or "").strip() or None,
        lineup=body.lineup.model_dump() if body.lineup is not None else None,
        created_at=now,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{post_id}")
def delete_post(post_id: int, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    p = db.get(BoardPost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")
    assert_owner_or_admin(c, p.kakao_id)
    # 글 삭제 시 딸린 댓글·좋아요도 함께 제거.
    db.query(BoardComment).filter(BoardComment.post_id == post_id).delete()
    db.query(BoardLike).filter(BoardLike.post_id == post_id).delete()
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
def create_comment(
    post_id: int,
    body: schemas.BoardCommentCreate,
    caller_: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    if db.get(BoardPost, post_id) is None:
        raise HTTPException(status_code=404, detail="post not found")
    c = BoardComment(
        post_id=post_id,
        kakao_id=effective_kakao_id(caller_, body.kakao_id),
        author=resolve_name(db, body.author.strip()),
        message=body.message.strip(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    caller_: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    c = db.get(BoardComment, comment_id)
    if c is None:
        raise HTTPException(status_code=404, detail="comment not found")
    assert_owner_or_admin(caller_, c.kakao_id)
    db.delete(c)
    db.commit()
    return {"deleted": 1}
