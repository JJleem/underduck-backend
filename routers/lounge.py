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
import hashlib
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

# 댓글에 쓰는 익명 이름 풀.
#
# 규칙: 팀원 누구도 지칭하지 않고, 놀림으로 읽힐 여지가 없을 것. 그래서 실력·출전
# 시간처럼 실제로 사람마다 다른 것은 넣지 않았다(익명이라도 콕 집힌 기분이 든다).
# 아마추어 축구면 다 겪는 것, 오리, 그리고 실없는 것들로 채웠다.
#
# ⚠️ 이 목록을 고치면 **이미 올라온 글의 이름도 같이 바뀐다** — 이름은 저장하지 않고
#    그때그때 계산한다. 사람이 뒤바뀌지는 않으니(글 안에서는 여전히 1:1) 표시만 달라진다.
ANON_NAMES = [
    # 오리
    "물갈퀴", "꽥꽥이", "뒤뚱이", "부리부리", "깃털부자", "물장구대장",
    "삑삑이", "백조지망생", "청둥오리", "목욕중인오리", "알품은오리", "오리발내밀기",
    # 축구
    "무회전킥", "왼발의추억", "오버헤드꿈나무", "헤딩은무서워", "코너킥장인",
    "프리킥연습생", "논스톱발리", "크로스바친구", "골대와친함", "드리블배우는중",
    "골닷컴", "빌드업중",
    # 경기 전후
    "파스냄새폴폴", "물통지킴이", "스트레칭중", "아이싱중", "근육통환자",
    "물집장인", "워밍업장인", "축구화지름신", "정강이보호대", "양말두겹",
    "인조잔디알러지", "하프타임간식", "경기전라면금지", "골넣고싶다",
    "벤치의철학자", "샤워실1등",
]
# 글의 작성자 자리에는 목록이든 상세든 언제나 "익명"이 온다.
POST_LABEL = "익명"
# "글쓴이"는 **댓글에만** 붙는 관계 표시다 — 이 댓글을 단 사람이 글쓴이라는 뜻.
# 글 헤더에까지 쓰면 "글쓴이 · 3시간 전"이 되어 하나 마나 한 말이 된다.
AUTHOR_LABEL = "글쓴이"


def _alias_pool(post_id: int) -> list[str]:
    """이 글에서 쓸 이름 순서.

    글 id 로 섞는다 — 같은 글에서는 언제 불러도 같은 순서라 이름이 안 흔들리고,
    글이 바뀌면 순서도 바뀌어 **같은 사람이 글마다 다른 이름**을 받는다.
    (순서대로 그냥 나눠 주면 첫 댓글자는 어느 글에서나 같은 이름이 된다)

    random.shuffle 대신 해시 정렬을 쓰는 이유: 파이썬 버전이 바뀌어도 결과가 같다.
    """
    return sorted(ANON_NAMES, key=lambda n: hashlib.md5(f"{post_id}:{n}".encode()).hexdigest())


def _labels(post: LoungePost, comments: list[LoungeComment]) -> dict[str, str]:
    """이 글 안에서만 통하는 kakao_id → 표시 이름.

    글쓴이는 언제나 "글쓴이"다. 나머지는 **댓글에 처음 등장한 순서대로** 풀에서
    하나씩 받는다(한 사람이 여러 번 달아도 이름은 하나로 유지된다).
    """
    labels = {post.kakao_id: AUTHOR_LABEL}
    pool = _alias_pool(post.id)
    n = 0
    for c in comments:
        if c.kakao_id in labels:
            continue
        name = pool[n % len(pool)]
        # 풀보다 사람이 많으면 한 바퀴 더 돈다 — 이름이 겹치면 안 되므로 숫자를 붙인다.
        labels[c.kakao_id] = name if n < len(pool) else f"{name} {n // len(pool) + 1}"
        n += 1
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
        icon=p.icon,
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
            p, c, label=POST_LABEL, comment_count=counts.get(p.id, 0), with_body=False
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
            parent_id=r.parent_id,
            author_label=labels.get(r.kakao_id, POST_LABEL),
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
        label=POST_LABEL,
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
        icon=body.icon,
        title=body.title.strip(),
        body=body.body.strip(),
        status="received",
        created_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _post_out(p, c, label=POST_LABEL, comment_count=0, with_body=True)


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
    return _post_out(p, admin, label=POST_LABEL, comment_count=count or 0, with_body=True)


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

    # 대댓글이면 부모를 확인한다. 깊이는 1단까지만 — 대댓글에 또 달면 부모로 접어
    # 올린다(막아버리면 "답글의 답글"을 쓰려던 사람이 갈 데가 없다).
    parent_id = None
    if body.parent_id is not None:
        parent = db.get(LoungeComment, body.parent_id)
        if parent is None or parent.post_id != post_id:
            raise HTTPException(status_code=404, detail="parent comment not found")
        parent_id = parent.parent_id or parent.id

    kakao_id, author = _require_author(c, db)
    row = LoungeComment(
        post_id=post_id,
        parent_id=parent_id,
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
        parent_id=row.parent_id,
        author_label=_labels(p, rows).get(row.kakao_id, POST_LABEL),
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
    # 부모를 지우면 딸린 대댓글도 함께 사라진다. 남겨두면 무슨 말에 대한
    # 답인지 알 수 없는 댓글만 떠돈다.
    db.query(LoungeComment).filter(LoungeComment.parent_id == row.id).delete()
    db.delete(row)
    db.commit()
    return {"deleted": 1}
