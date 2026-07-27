"""보안 조치 회귀 테스트.

핵심 전제: **신원 헤더가 없으면 기존과 100% 동일하게 동작한다.**
프론트 컷오버 전에 배포해도 기능 영향이 없어야 하므로 그 하위 호환성을 여기서 고정한다.
"""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import schemas
import security
from deps import Caller, assert_owner_or_admin, effective_kakao_id
from main import app

client = TestClient(app)
AUTH = {"X-Underduck-Secret": "test-secret"}


@pytest.fixture(autouse=True)
def _clear_throttle():
    security.reset_throttle()
    yield
    security.reset_throttle()


# ── 문서 라우트 비공개 ──
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_not_served(path):
    assert client.get(path).status_code == 404


# ── 인증 실패 스로틀 ──
def test_repeated_auth_failures_are_throttled():
    codes = [
        client.get("/api/underduck/_authcheck", headers={"X-Underduck-Secret": "nope"}).status_code
        for _ in range(15)
    ]
    assert codes[0] == 401
    assert 429 in codes, "인증 실패가 반복돼도 차단되지 않았다"


def test_valid_secret_is_never_throttled():
    # 올바른 시크릿은 실패 카운터를 올리지 않으므로 정상 트래픽에 영향이 없어야 한다.
    for _ in range(30):
        assert client.get("/api/underduck/_authcheck", headers=AUTH).status_code == 200


# ── 보안 헤더 ──
def test_security_headers_present():
    h = client.get("/api/underduck/_authcheck", headers=AUTH).headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "no-referrer"


# ── URL 스킴 검증 (저장형 XSS) ──
@pytest.mark.parametrize(
    "bad",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "java\tscript:alert(1)",   # 제어문자 우회
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox(1)",
    ],
)
def test_dangerous_url_schemes_rejected(bad):
    with pytest.raises(ValidationError):
        schemas.BoardPostCreate(kakao_id="1", author="가", title="t", youtube_url=bad)


@pytest.mark.parametrize(
    "ok",
    [
        "https://www.youtube.com/watch?v=abc",
        "http://youtu.be/abc",
        "youtube.com/watch?v=abc",   # 스킴 없는 값도 기존처럼 통과
    ],
)
def test_normal_urls_still_accepted(ok):
    assert schemas.BoardPostCreate(
        kakao_id="1", author="가", title="t", youtube_url=ok
    ).youtube_url == ok


# ── 입력 길이 상한 ──
def test_oversized_body_rejected():
    with pytest.raises(ValidationError):
        schemas.BoardCommentCreate(kakao_id="1", author="가", message="x" * 10_001)


def test_normal_body_accepted():
    assert schemas.BoardCommentCreate(kakao_id="1", author="가", message="x" * 500)


# ── 신원/권한 로직 (하위 호환이 핵심) ──
def test_legacy_mode_preserves_behaviour():
    """헤더가 없으면 본문 kakao_id를 그대로 쓰고, 소유자 검사도 하지 않는다."""
    legacy = Caller(kakao_id=None, role=None)
    assert effective_kakao_id(legacy, "from-body") == "from-body"
    assert assert_owner_or_admin(legacy, "someone-else") is None


def test_identity_header_overrides_body_kakao_id():
    c = Caller(kakao_id="real-user", role="member")
    assert effective_kakao_id(c, "spoofed") == "real-user"


def test_non_owner_cannot_delete():
    c = Caller(kakao_id="user-a", role="member")
    with pytest.raises(Exception) as e:
        assert_owner_or_admin(c, "user-b")
    assert e.value.status_code == 403


def test_owner_and_admin_can_delete():
    assert assert_owner_or_admin(Caller("user-a", "member"), "user-a") is None
    assert assert_owner_or_admin(Caller("user-a", "admin"), "user-b") is None


def test_rows_without_author_are_still_deletable():
    """kakao_id가 NULL인 구 데이터가 삭제 불가 상태로 남지 않아야 한다."""
    assert assert_owner_or_admin(Caller("user-a", "member"), None) is None


# ── 관리자 전용 엔드포인트 ──
def test_admin_endpoint_rejects_member_role():
    r = client.put(
        "/api/underduck/notice",
        headers={**AUTH, "X-Underduck-User": "u1", "X-Underduck-Role": "member"},
        json={"date": "2026-07-27", "title": "t", "content": "c"},
    )
    assert r.status_code == 403


# ── kakao_id 가명화 ────────────────────────────────────────────────
def test_pseudonym_is_deterministic_and_one_way():
    a = security.pseudonymize("3812457")
    assert a == security.pseudonymize("3812457")      # 결정론적 → 등호비교/UNIQUE 동작
    assert a != security.pseudonymize("3812458")
    assert "3812457" not in a                          # 원본이 남지 않는다
    assert security.is_pseudonym(a) and len(a) == 64


def test_pseudonymize_is_idempotent():
    """이미 pid인 값은 재해싱하지 않는다 → 프론트 배포 전후 어느 쪽 값이 와도 동일 신원."""
    pid = security.pseudonymize("3812457")
    assert security.pseudonymize(pid) == pid


def test_kakao_id_pseudonymized_at_schema_boundary():
    body = schemas.BoardCommentCreate(kakao_id="3812457", author="가", message="m")
    assert body.kakao_id == security.pseudonymize("3812457")
    assert body.kakao_id != "3812457"


def test_resolve_endpoint_returns_pid():
    r = client.post("/api/underduck/users/resolve", headers=AUTH, json={"kakao_id": "3812457"})
    assert r.status_code == 200
    assert r.json() == {"kakao_id": security.pseudonymize("3812457")}


def test_resolve_does_not_accept_raw_id_in_query():
    """원본 ID를 URL에 실어 pid를 얻는 경로가 없어야 한다.

    nginx access log는 쿼리스트링을 그대로 기록하므로, GET으로 변환이 되면
    로그인할 때마다 원본 카카오 ID가 서버 로그에 평문으로 쌓인다.
    (지금은 GET /users/{kakao_id} 로 흘러가 404가 난다 — 변환은 일어나지 않는다.)
    """
    r = client.get("/api/underduck/users/resolve?kakao_id=3812457", headers=AUTH)
    assert r.status_code != 200
    assert security.pseudonymize("3812457") not in r.text


def test_identity_header_accepts_raw_or_pid():
    """전환 기간에 프론트가 원본을 보내든 pid를 보내든 같은 신원으로 해석돼야 한다."""
    from starlette.datastructures import Headers
    from starlette.requests import Request as StarletteRequest

    from deps import caller as caller_dep

    def mk(v):
        scope = {"type": "http", "headers": Headers({"X-Underduck-User": v}).raw}
        return caller_dep(StarletteRequest(scope))

    pid = security.pseudonymize("3812457")
    assert mk("3812457").kakao_id == pid
    assert mk(pid).kakao_id == pid
