from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Notice
from deps import require_admin, require_underduck

router = APIRouter(
    prefix="/api/underduck/notice",
    tags=["notice"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=schemas.NoticeOut | None)
def get_notice(db: Session = Depends(get_db)):
    # 단일 활성 공지(가장 낮은 id). 없으면 null.
    return db.scalars(select(Notice).order_by(Notice.id)).first()


@router.put("", response_model=schemas.NoticeOut, dependencies=[Depends(require_admin)])
def update_notice(body: schemas.NoticeUpdate, db: Session = Depends(get_db)):
    row = db.scalars(select(Notice).order_by(Notice.id)).first()
    if row is None:
        row = Notice()
        db.add(row)
    row.date = body.date
    row.title = body.title
    row.content = body.content
    row.important = body.important
    row.location = body.location
    db.commit()
    db.refresh(row)
    return row
