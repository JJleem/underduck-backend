"""보안 미들웨어·유틸 (인증 실패 스로틀링, 보안 헤더, URL 스킴 검증).

설계 원칙: **기존 API 계약을 바꾸지 않는다.**
- 스로틀은 "인증에 실패한 요청"만 센다 → 정상 트래픽은 영향 0.
- 보안 헤더는 응답 본문/상태코드를 건드리지 않는다.
"""
import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── 인증 실패 스로틀 ────────────────────────────────────────────────
# nginx의 limit_req(전역)와 별개로, 앱 레벨에서 시크릿 브루트포스를 직접 차단.
# 단일 uvicorn 프로세스(run.py, worker 1개) 전제라 인메모리로 충분.
_FAIL_WINDOW_SEC = 300      # 5분 슬라이딩 윈도우
_FAIL_MAX = 10              # 윈도우 내 인증 실패 10회 → 이후 429
_MAX_TRACKED_IPS = 10_000   # 메모리 고갈 방지 상한

_failures: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    """nginx가 넣어주는 X-Forwarded-For의 첫 IP. 없으면 소켓 주소."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(ip: str, now: float) -> list[float]:
    hits = [t for t in _failures.get(ip, []) if now - t < _FAIL_WINDOW_SEC]
    if hits:
        _failures[ip] = hits
    else:
        _failures.pop(ip, None)
    return hits


def is_throttled(request: Request) -> bool:
    """이 IP가 최근 인증 실패 한도를 넘겼는가."""
    return len(_prune(client_ip(request), time.monotonic())) >= _FAIL_MAX


def record_auth_failure(request: Request) -> None:
    """인증 실패 1회 기록. 성공한 요청은 절대 호출되지 않으므로 정상 사용자 영향 없음."""
    now = time.monotonic()
    ip = client_ip(request)
    hits = _prune(ip, now)

    if ip not in _failures and len(_failures) >= _MAX_TRACKED_IPS:
        # 가장 오래된 항목부터 정리 (추적 테이블 자체가 DoS 벡터가 되지 않도록)
        for stale in sorted(_failures, key=lambda k: _failures[k][-1])[:_MAX_TRACKED_IPS // 10]:
            _failures.pop(stale, None)

    hits.append(now)
    _failures[ip] = hits


def reset_throttle() -> None:
    """테스트용."""
    _failures.clear()


# ── 보안 헤더 ──────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """JSON API용 최소 보안 헤더. 응답 본문/상태코드는 건드리지 않는다."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        # HTTPS는 nginx가 종단. 프록시가 https로 넘겼을 때만 HSTS를 붙인다.
        if request.headers.get("X-Forwarded-Proto") == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


# ── URL 스킴 검증 ──────────────────────────────────────────────────
# 저장형 XSS 방지: javascript:/data:/vbscript: 등 실행 가능한 스킴을 차단.
# http/https 및 "스킴 없는 값"은 그대로 통과 → 기존 데이터/입력과 호환.
_CTRL = re.compile(r"[\x00-\x20\x7f]")
_SCHEME = re.compile(r"^([a-z][a-z0-9+.\-]*):", re.IGNORECASE)
_ALLOWED_SCHEMES = {"http", "https"}


def validate_url(value: str | None) -> str | None:
    """실행 가능한 스킴이면 ValueError. 그 외(http/https/스킴없음)는 원본 그대로 반환."""
    if value is None:
        return None
    # "java\tscript:..." 같은 우회를 막기 위해 제어문자를 제거한 뒤 스킴을 판정한다.
    probe = _CTRL.sub("", value)
    m = _SCHEME.match(probe)
    if m and m.group(1).lower() not in _ALLOWED_SCHEMES:
        raise ValueError(f"허용되지 않는 URL 스킴입니다: {m.group(1)}")
    return value
