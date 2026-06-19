"""stats 집계 엔드포인트 회귀 테스트 (SQLite in-memory + get_db 오버라이드).

matches 명단(골/도움/참석)과 mom_vote(공격/수비 부문 투표)에서 선수별 통계를
매 요청 집계하는지 검증한다.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.connection import Base, get_db
from db import models
from main import app

HEADERS = {"X-Underduck-Secret": "test-secret"}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # 단일 연결 공유: in-memory DB가 TestClient 스레드에서도 유지
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    db = TestingSession()
    db.add_all([
        models.Roster(no="7", name="홍길동", pos="FW", status="활동"),
        models.Roster(no="10", name="김철수", pos="MF", status="활동"),
        models.Roster(no="4", name="박영희", pos="DF", status="활동"),
    ])
    db.add_all([
        models.Match(match_id=0, goals="홍길동,홍길동", assists="박영희,",
                     attendees="홍길동,김철수,박영희"),
        models.Match(match_id=1, goals="김철수", assists="김철수",
                     attendees="홍길동,김철수"),
        models.Match(match_id=2, goals="게스트", attendees="게스트"),  # roster 밖
    ])
    db.add_all([
        # 경기0 공격: 홍길동 2표 vs 김철수 1표 → 홍길동
        models.MomVote(match_id=0, voter_name="a", voted_for="홍길동", vote_type="공격"),
        models.MomVote(match_id=0, voter_name="b", voted_for="홍길동", vote_type="공격"),
        models.MomVote(match_id=0, voter_name="c", voted_for="김철수", vote_type="공격"),
        # 경기0 수비: 박영희 → 박영희
        models.MomVote(match_id=0, voter_name="a", voted_for="박영희", vote_type="수비"),
    ])
    db.commit()

    app.dependency_overrides[get_db] = lambda: TestingSession()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_stats_requires_auth(client):
    assert client.get("/api/underduck/stats").status_code == 401


def test_stats_aggregation(client):
    rows = client.get("/api/underduck/stats", headers=HEADERS).json()
    by = {r["name"]: r for r in rows}

    # 골: 한 경기 같은 이름 2번이면 2골
    assert by["홍길동"]["goals"] == 2
    assert by["김철수"]["goals"] == 1
    # 출전: 참석 명단 등장 경기 수
    assert by["홍길동"]["apps"] == 2
    assert by["박영희"]["apps"] == 1
    # 도움
    assert by["김철수"]["assists"] == 1
    assert by["박영희"]["assists"] == 1
    # mom: 공격/수비 부문별 최다득표 1회씩
    assert by["홍길동"]["mom"] == 1
    assert by["박영희"]["mom"] == 1
    assert by["김철수"]["mom"] == 0
    # roster 정보(no/pos) 채워짐
    assert by["홍길동"]["no"] == "7" and by["홍길동"]["pos"] == "FW"
    # roster 밖 게스트도 누락되지 않고 no/pos는 비어있음
    assert by["게스트"]["goals"] == 1 and by["게스트"]["no"] is None
