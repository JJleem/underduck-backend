import hmac
import os
from dataclasses import dataclass

from fastapi import HTTPException, Request

import security

_UNDERDUCK_API_SECRET = os.environ.get("UNDERDUCK_API_SECRET", "")


def require_underduck(request: Request):
    """X-Underduck-Secret 헤더를 공유 비밀키와 상수시간 비교. 불일치/미설정 시 401.

    같은 IP에서 인증 실패가 반복되면 429로 막는다(시크릿 브루트포스 차단).

    검증 순서가 중요하다: **시크릿을 먼저 확인**하고, 틀린 요청만 스로틀 대상으로 삼는다.
    스로틀을 앞에 두면 프론트 서버(단일 IP)에서 실패가 몇 번 나는 순간 정상 요청까지
    429로 막혀 서비스 전체가 죽는다. 올바른 시크릿은 어떤 경우에도 통과해야 한다.
    """
    key = request.headers.get("X-Underduck-Secret", "")
    if _UNDERDUCK_API_SECRET and hmac.compare_digest(key, _UNDERDUCK_API_SECRET):
        return

    security.record_auth_failure(request)
    if security.is_throttled(request):
        raise HTTPException(status_code=429, detail="Too Many Requests")
    raise HTTPException(status_code=401, detail="Unauthorized")


# ── 호출자 신원 (프론트가 세션에서 꺼내 헤더로 전달) ──────────────────
#
# 공유 시크릿은 "어느 서비스가 불렀나"만 증명할 뿐 "어떤 사용자인가"는 증명하지 못한다.
# 그래서 신원은 별도 헤더로 받는다. 요청 **본문**의 kakao_id는 클라이언트가 자유롭게
# 조작할 수 있으므로 권한 판단에 절대 쓰지 않는다.
#
#   X-Underduck-User: <kakao_id>      # 프론트 서버가 세션에서 꺼낸 값 (본문 값 금지)
#   X-Underduck-Role: member | admin
#
# 하위 호환: 헤더가 없으면 기존과 100% 동일하게 동작한다(검사 생략).
# 프론트가 헤더를 붙이기 시작하는 순간부터 소유자/관리자 검사가 켜진다.
_USER_HEADER = "X-Underduck-User"
_ROLE_HEADER = "X-Underduck-Role"


@dataclass(frozen=True)
class Caller:
    kakao_id: str | None   # None = 프론트가 아직 신원 헤더를 안 보냄(레거시 모드)
    role: str | None       # None = 레거시 모드

    @property
    def is_identified(self) -> bool:
        return self.kakao_id is not None or self.role is not None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def caller(request: Request) -> Caller:
    """신원 헤더를 Caller로 변환. 헤더가 없으면 레거시 모드(검사 생략)."""
    uid = (request.headers.get(_USER_HEADER) or "").strip() or None
    role = (request.headers.get(_ROLE_HEADER) or "").strip().lower() or None
    return Caller(kakao_id=uid, role=role)


def require_admin(request: Request) -> Caller:
    """관리자 전용 엔드포인트. 신원 헤더가 없으면 통과(레거시 호환), 있으면 admin만 허용."""
    c = caller(request)
    if c.is_identified and not c.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: admin only")
    return c


def assert_owner_or_admin(c: Caller, owner_kakao_id: str | None) -> None:
    """작성자 본인 또는 관리자만 허용.

    - 신원 헤더가 없으면(레거시) 통과 → 기존 동작 유지.
    - 대상 행에 작성자 정보가 없으면(구 데이터, kakao_id NULL) 통과 → 삭제 불가 행 방지.
    """
    if not c.is_identified or c.is_admin:
        return
    if owner_kakao_id and c.kakao_id != owner_kakao_id:
        raise HTTPException(status_code=403, detail="Forbidden: not the author")


def effective_kakao_id(c: Caller, body_kakao_id: str) -> str:
    """저장에 쓸 kakao_id. 신원 헤더가 있으면 **헤더 값이 본문을 덮어쓴다**(사칭 차단)."""
    return c.kakao_id or body_kakao_id
