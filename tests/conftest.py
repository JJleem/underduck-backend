import os

# import 시점에 db.connection / deps 가 읽는 환경변수를 테스트 기본값으로 설정.
# create_engine 은 lazy 라 실제 DB 없이도 import 가능(쿼리 시에만 접속).
os.environ.setdefault(
    "UNDERDUCK_DATABASE_URL",
    "postgresql://underduck:underduck@localhost:5432/underduck",
)
os.environ.setdefault("UNDERDUCK_API_SECRET", "test-secret")
os.environ.setdefault("UNDERDUCK_ID_PEPPER", "test-pepper")

import pytest  # noqa: E402  (환경변수 설정 후에 import 해야 한다)


@pytest.fixture(autouse=True)
def _reset_auth_throttle():
    """인증 실패 스로틀은 프로세스 전역 상태 → 테스트 간 누수 방지."""
    import security

    security.reset_throttle()
    yield
    security.reset_throttle()
