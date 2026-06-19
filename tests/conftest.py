import os

# import 시점에 db.connection / deps 가 읽는 환경변수를 테스트 기본값으로 설정.
# create_engine 은 lazy 라 실제 DB 없이도 import 가능(쿼리 시에만 접속).
os.environ.setdefault(
    "UNDERDUCK_DATABASE_URL",
    "postgresql://underduck:underduck@localhost:5432/underduck",
)
os.environ.setdefault("UNDERDUCK_API_SECRET", "test-secret")
