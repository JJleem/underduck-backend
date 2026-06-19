from fastapi import APIRouter, Depends
from sqlalchemy import text

from db.connection import SessionLocal
from deps import require_underduck

router = APIRouter(prefix="/api/underduck", tags=["underduck"])


@router.get("/health")
def health(_=Depends(require_underduck)):
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"ok": True, "db": "connected"}
    except Exception as e:
        return {"ok": False, "db": str(e)}


@router.get("/_authcheck")
def authcheck(_=Depends(require_underduck)):
    return {"authed": True}
