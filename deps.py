import hmac
import os

from fastapi import HTTPException, Request

_UNDERDUCK_API_SECRET = os.environ.get("UNDERDUCK_API_SECRET", "")


def require_underduck(request: Request):
    """X-Underduck-Secret 헤더를 공유 비밀키와 상수시간 비교. 불일치/미설정 시 401."""
    key = request.headers.get("X-Underduck-Secret", "")
    if not _UNDERDUCK_API_SECRET or not hmac.compare_digest(key, _UNDERDUCK_API_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")
