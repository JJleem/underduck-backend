import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text

from db.connection import SessionLocal
from deps import require_underduck

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/underduck", tags=["underduck"])


@router.get("/health")
def health(_=Depends(require_underduck)):
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"ok": True, "db": "connected"}
    except Exception:
        # 예외 원문에는 DB 호스트/유저명/DB명이 들어간다. 응답에는 노출하지 않고 로그로만 남긴다.
        logger.exception("health check failed")
        return {"ok": False, "db": "error"}


@router.get("/_authcheck")
def authcheck(_=Depends(require_underduck)):
    return {"authed": True}
