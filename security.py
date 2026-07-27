"""보안 미들웨어·유틸 (인증 실패 스로틀링, 보안 헤더, URL 스킴 검증).

설계 원칙: **기존 API 계약을 바꾸지 않는다.**
- 스로틀은 "인증에 실패한 요청"만 센다 → 정상 트래픽은 영향 0.
- 보안 헤더는 응답 본문/상태코드를 건드리지 않는다.
"""
import hashlib
import hmac
import os
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


# ── kakao_id 가명화 ────────────────────────────────────────────────
# 카카오 원본 ID는 영구 식별자라 유출되면 회수가 불가능하다. 그래서 **저장하지 않는다**.
# 대신 서버만 아는 pepper로 HMAC-SHA256 치환한 값(pid)을 신원으로 쓴다.
#
#   pid = HMAC-SHA256(UNDERDUCK_ID_PEPPER, kakao_id)  → 64자 소문자 hex
#
# 결정론적이라 등호 비교·UNIQUE 제약·upsert가 전부 그대로 동작한다(기능 무손실).
# 단방향이라 DB나 API 응답이 통째로 유출돼도 카카오 계정을 역산할 수 없다.
#
# 한계(정확히 알고 쓸 것): 원본 ID는 로그인 시 요청 본문으로 **전달은 된다**.
# 없앨 수 있는 것은 "영구 저장"이지 "전송"이 아니다. 서버는 받는 즉시 해시하고 버린다.
_ID_PEPPER = os.environ.get("UNDERDUCK_ID_PEPPER", "")
if not _ID_PEPPER:
    raise RuntimeError(
        "UNDERDUCK_ID_PEPPER 환경변수가 설정되지 않았습니다. "
        "`openssl rand -hex 32` 값을 서버 .env에 넣으세요. "
        "이 값을 분실하면 기존 회원의 신원 연결이 끊깁니다(글·투표 소유권 소실)."
    )

_PID_RE = re.compile(r"^[0-9a-f]{64}$")


def is_pseudonym(value: str) -> bool:
    """이미 가명화된 값(64자 hex)인가. 카카오 원본 ID는 10자리 안팎의 숫자라 겹치지 않는다."""
    return bool(_PID_RE.match(value))


def pseudonymize(kakao_id: str | None) -> str | None:
    """카카오 원본 ID → 가명 ID(pid).

    멱등: 이미 pid인 값이 들어오면 재해싱하지 않고 그대로 돌려준다.
    덕분에 프론트가 원본을 보내든 pid를 보내든 같은 신원으로 해석되어,
    프론트 배포 전후 어느 시점에도 쓰기가 깨지지 않는다(무중단 전환).
    """
    if not kakao_id:
        return kakao_id
    value = kakao_id.strip()
    if is_pseudonym(value):
        return value
    return hmac.new(_ID_PEPPER.encode(), value.encode(), hashlib.sha256).hexdigest()
