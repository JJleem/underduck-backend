from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Media
from deps import require_admin, require_underduck

router = APIRouter(
    prefix="/api/underduck/media",
    tags=["media"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.MediaOut])
def list_media(db: Session = Depends(get_db)):
    return db.scalars(select(Media).order_by(Media.id)).all()


@router.post("", response_model=schemas.MediaOut, status_code=201, dependencies=[Depends(require_admin)])
def create_media(body: schemas.MediaCreate, db: Session = Depends(get_db)):
    m = Media(type=body.type, url=body.url, title=body.title, uploaded_at=datetime.now(timezone.utc))
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{media_id}", dependencies=[Depends(require_admin)])
def delete_media(media_id: int, db: Session = Depends(get_db)):
    m = db.get(Media, media_id)
    if m is None:
        raise HTTPException(status_code=404, detail="media not found")
    db.delete(m)
    db.commit()
    return {"deleted": 1}
