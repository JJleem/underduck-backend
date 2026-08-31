"""사랑방 — 애로사항·건의를 익명으로 남기는 게시판.

이 라우터의 존재 이유는 **익명화**다. 다른 게시판과 달리 세 가지를 지킨다.

  1. 실명(`author`)은 저장하되 **운영진 요청에만** 응답에 싣는다.
     프론트에서 가리는 건 익명이 아니다 — 개발자 도구로 그대로 보인다.
  2. 표시 이름은 서버가 **글 단위로** 매긴다("글쓴이", "덕민 1", "덕민 2").
     글이 달라지면 번호도 새로 매겨진다 — 글을 여러 개 쓴 사람이 번호로
     추적되지 않게 하려는 것이다.
  3. `kakao_id` 는 응답에 절대 넣지 않는다. 소유권 판단은 여기서 끝내고
     프론트에는 `mine` 불리언만 준다.

그래서 Out 스키마를 ORM 에서 `model_validate` 로 통째로 만들지 않는다.
필드를 하나씩 채워야 실명이 새려면 명시적으로 한 줄을 써야 한다.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import LoungeComment, LoungePost
from deps import Caller, assert_owner_or_admin, caller, require_admin, require_underduck
from naming import caller_real_name

router = APIRouter(
    prefix="/api/underduck/lounge",
    tags=["lounge"],
    dependencies=[Depends(require_underduck)],
)

# 익명 이름의 접두어. 바꾸고 싶으면 여기만 고치면 된다.
ANON_PREFIX = "덕민"
AUTHOR_LABEL = "글쓴이"
LIST_LABEL = "익명"


def _labels(post: LoungePost, comments: list[LoungeComment]) -> dict[str, str]:
    """이 글 안에서만 통하는 kakao_id → 표시 이름.

    글쓴이는 언제나 "글쓴이"고, 나머지는 **댓글에 처음 등장한 순서대로** 번호를 받는다.
    (한 사람이 여러 번 달아도 번호는 하나로 유지된다)
    """
    labels = {post.kakao_id: AUTHOR_LABEL}
    n = 0
    for c in comments:
        if c.kakao_id in labels:
            continue
        n += 1
        labels[c.kakao_id] = f"{ANON_PREFIX} {n}"
    return labels


def _post_out(
    p: LoungePost,
    c: Caller,
    *,
    label: str,
    comment_count: int,
    with_body: bool,
    comments: list[schemas.LoungeCommentOut] | None = None,
) -> schemas.LoungePostOut:
    return schemas.LoungePostOut(
        id=p.id,
        category=p.category,
        title=p.title,
        body=p.body if with_body else None,
        status=p.status,
        author_label=label,
        # 실명이 나가는 유일한 지점. 운영진이 아니면 None.
        author=p.author if c.is_admin else None,
        mine=bool(c.kakao_id) and c.kakao_id == p.kakao_id,
        comment_count=comment_count,
        admin_reply=p.admin_reply,
        admin_reply_author=p.admin_reply_author,
        admin_reply_at=p.admin_reply_at,
        created_at=p.created_at,
        comments=comments,
    )


@router.get("", response_model=list[schemas.LoungePostOut])
def list_posts(c: Caller = Depends(caller), db: Session = Depends(get_db)):
    """최신순 목록. 본문은 싣지 않고, 작성자는 전부 "익명"으로 나간다.

    목록에서까지 글 단위 라벨("덕민 1")을 계산하면 글 수만큼 댓글을 훑어야 하고,
    얻는 것도 없다 — 목록엔 댓글이 안 보인다.
    """
    counts = dict(
        db.execute(
            select(LoungeComment.post_id, func.count(LoungeComment.id)).group_by(
                LoungeComment.post_id
            )
        ).all()
    )
    posts = db.scalars(select(LoungePost).order_by(LoungePost.id.desc())).all()
    return [
        _post_out(
            p, c, label=LIST_LABEL, comment_count=counts.get(p.id, 0), with_body=False
        )
        for p in posts
    ]


@router.get("/{post_id}", response_model=schemas.LoungePostOut)
def get_post(post_id: int, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    p = db.get(LoungePost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")

    rows = db.scalars(
        select(LoungeComment)
        .where(LoungeComment.post_id == post_id)
        .order_by(LoungeComment.id)
    ).all()
    labels = _labels(p, rows)

    comments = [
        schemas.LoungeCommentOut(
            id=r.id,
            author_label=labels.get(r.kakao_id, LIST_LABEL),
            author=r.author if c.is_admin else None,
            mine=bool(c.kakao_id) and c.kakao_id == r.kakao_id,
            message=r.message,
            emoticon=r.emoticon,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return _post_out(
        p,
        c,
        label=AUTHOR_LABEL,
        comment_count=len(rows),
        with_body=True,
        comments=comments,
    )


def _require_author(c: Caller, db: Session) -> tuple[str, str]:
    """신원 헤더에서 (kakao_id, 실명)을 꺼낸다. 사랑방은 레거시 모드를 허용하지 않는다.

    다른 게시판은 헤더가 없으면 본문의 kakao_id 로 넘어가지만, 여기서는 그러면
    "누가 썼는지 운영진은 안다"는 약속이 깨진다. 신원이 없으면 아예 못 쓴다.
    """
    if not c.kakao_id:
        raise HTTPException(status_code=401, detail="identity required")
    name = caller_real_name(db, c.kakao_id)
    if not name:
        raise HTTPException(status_code=400, detail="로스터에 등록된 이름을 찾을 수 없습니다.")
    return c.kakao_id, name


@router.post("", response_model=schemas.LoungePostOut, status_code=201)
def create_post(
    body: schemas.LoungePostCreate,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    kakao_id, author = _require_author(c, db)
    p = LoungePost(
        kakao_id=kakao_id,
        author=author,
        category=body.category,
        title=body.title.strip(),
        body=body.body.strip(),
        status="received",
        created_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _post_out(p, c, label=AUTHOR_LABEL, comment_count=0, with_body=True)


@router.patch("/{post_id}", response_model=schemas.LoungePostOut)
def update_post(
    post_id: int,
    body: schemas.LoungePostPatch,
    admin: Caller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """운영진 전용 — 상태 변경과 답변.

    답변이 달린다는 게 보여야 다음 사람이 쓴다. 답변 없는 건의함은 곧 빈 페이지가 된다.
    """
    if body.status is None and body.admin_reply is None:
        raise HTTPException(status_code=400, detail="nothing to update")
    p = db.get(LoungePost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")

    now = datetime.now(timezone.utc)
    if body.status is not None:
        p.status = body.status
    if body.admin_reply is not None:
        reply = body.admin_reply.strip()
        p.admin_reply = reply or None
        # 답변자 이름은 공개해도 된다 — 누가 답했는지는 오히려 보여야 한다.
        p.admin_reply_author = caller_real_name(db, admin.kakao_id) if reply else None
        p.admin_reply_at = now if reply else None
    p.updated_at = now
    db.commit()
    db.refresh(p)

    count = db.scalar(
        select(func.count(LoungeComment.id)).where(LoungeComment.post_id == post_id)
    )
    return _post_out(p, admin, label=AUTHOR_LABEL, comment_count=count or 0, with_body=True)


@router.delete("/{post_id}")
def delete_post(post_id: int, c: Caller = Depends(caller), db: Session = Depends(get_db)):
    p = db.get(LoungePost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")
    assert_owner_or_admin(c, p.kakao_id)
    db.query(LoungeComment).filter(LoungeComment.post_id == post_id).delete()
    db.delete(p)
    db.commit()
    return {"deleted": 1}


# ── comments ──
@router.post("/{post_id}/comments", response_model=schemas.LoungeCommentOut, status_code=201)
def create_comment(
    post_id: int,
    body: schemas.LoungeCommentCreate,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    p = db.get(LoungePost, post_id)
    if p is None:
        raise HTTPException(status_code=404, detail="post not found")

    message = (body.message or "").strip() or None
    if not message and not body.emoticon:
        raise HTTPException(status_code=400, detail="댓글 내용이나 이모티콘이 필요합니다.")

    kakao_id, author = _require_author(c, db)
    row = LoungeComment(
        post_id=post_id,
        kakao_id=kakao_id,
        author=author,
        message=message,
        emoticon=body.emoticon,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # 방금 단 댓글의 라벨도 글 단위 규칙으로 다시 매긴다(그래야 화면과 어긋나지 않는다).
    rows = db.scalars(
        select(LoungeComment)
        .where(LoungeComment.post_id == post_id)
        .order_by(LoungeComment.id)
    ).all()
    return schemas.LoungeCommentOut(
        id=row.id,
        author_label=_labels(p, rows).get(row.kakao_id, LIST_LABEL),
        author=row.author if c.is_admin else None,
        mine=True,
        message=row.message,
        emoticon=row.emoticon,
        created_at=row.created_at,
    )


@router.delete("/{post_id}/comments/{comment_id}")
def delete_comment(
    post_id: int,
    comment_id: int,
    c: Caller = Depends(caller),
    db: Session = Depends(get_db),
):
    row = db.get(LoungeComment, comment_id)
    if row is None or row.post_id != post_id:
        raise HTTPException(status_code=404, detail="comment not found")
    assert_owner_or_admin(c, row.kakao_id)
    db.delete(row)
    db.commit()
    return {"deleted": 1}
