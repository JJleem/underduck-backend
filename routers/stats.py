from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from db.connection import get_db
from db.models import Stat
from deps import require_underduck

# ⚠️ stats는 시트 수식 산출물의 스냅샷(읽기전용). 시트 폐기 후 matches/mom_vote 집계 endpoint로 대체 필요.
router = APIRouter(
    prefix="/api/underduck/stats",
    tags=["stats"],
    dependencies=[Depends(require_underduck)],
)


@router.get("", response_model=list[schemas.StatOut])
def list_stats(db: Session = Depends(get_db)):
    return db.scalars(select(Stat).order_by(Stat.id)).all()
