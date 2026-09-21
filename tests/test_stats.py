"""stats 집계 엔드포인트 회귀 테스트 (SQLite in-memory + get_db 오버라이드).

matches 명단(골/도움/참석/MOM)에서 선수별 통계를 매 요청 집계하는지 검증한다.

MOM 은 확정 기록(matches.mom)에서 센다. 예전엔 mom_vote 에서 셌는데 투표가
없던 옛 경기의 MOM 이 통째로 빠져 화면과 어긋났다.
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
        # MOM: "/" 는 공격/수비 구분, "," 는 같은 부문 공동 수상. 둘 다 섞여 들어온다.
        models.Match(match_id=0, goals="홍길동,홍길동", assists="박영희,",
                     attendees="홍길동,김철수,박영희", mom="홍길동 / 박영희"),
        models.Match(match_id=1, goals="김철수", assists="김철수",
                     attendees="홍길동,김철수", mom="홍길동,김철수 / 박영희"),
        models.Match(match_id=2, goals="게스트", attendees="게스트"),  # roster 밖
        # 야유회: 경기가 아니라 행사다. goals 칸에 선수 대신 종목이 적힌다.
        models.Match(match_id=3, type="야유회", goals="바베큐,족구",
                     attendees="홍길동,김철수,박영희"),
        # 예정 경기: 출석 투표로 명단이 미리 차 있다. 아직 뛴 게 아니다.
        models.Match(match_id=4, result="예정", attendees="홍길동,김철수,박영희"),
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
    # mom: 확정 기록에서. "/" 와 "," 를 모두 풀어야 맞는 수가 나온다.
    #   홍길동 = 경기0 + 경기1 = 2   (경기1 은 "," 뒤가 아니라 앞)
    #   박영희 = 경기0 + 경기1 = 2   ("/" 뒤 — 쉼표로만 자르면 통째로 놓친다)
    #   김철수 = 경기1 = 1           ("," 로 묶인 공동 수상)
    assert by["홍길동"]["mom"] == 2
    assert by["박영희"]["mom"] == 2
    assert by["김철수"]["mom"] == 1
    # roster 정보(no/pos) 채워짐
    assert by["홍길동"]["no"] == "7" and by["홍길동"]["pos"] == "FW"
    # roster 밖 게스트도 누락되지 않고 no/pos는 비어있음
    assert by["게스트"]["goals"] == 1 and by["게스트"]["no"] is None


def test_outing_excluded(client):
    """야유회는 출전 수에도, 득점자에도 들어가지 않는다.

    goals 칸에 "바베큐,족구" 처럼 종목이 적혀 있어서 그대로 세면 그 종목들이
    1골짜리 선수로 순위에 올라온다. 실제 운영 데이터에서 다섯 개가 올라와 있었다.
    """
    rows = client.get("/api/underduck/stats", headers=HEADERS).json()
    names = {r["name"] for r in rows}
    assert "바베큐" not in names
    assert "족구" not in names

    by = {r["name"]: r for r in rows}
    # 홍길동은 0·1번 경기에만 출전. 야유회(3번)가 세지면 3이 된다.
    assert by["홍길동"]["apps"] == 2
    assert by["박영희"]["apps"] == 1


def test_upcoming_not_counted(client):
    """예정 경기는 명단이 차 있어도 출전 수에 넣지 않는다.

    출석 투표나 사전 입력으로 명단이 먼저 채워지기 때문에, 그대로 세면
    경기가 열리기도 전에 기록이 올라간다.
    """
    rows = client.get("/api/underduck/stats", headers=HEADERS).json()
    by = {r["name"]: r for r in rows}
    assert by["홍길동"]["apps"] == 2   # 0·1번만. 3(야유회)·4(예정) 제외
    assert by["박영희"]["apps"] == 1


# ───────────────────────── 시즌 필터 ─────────────────────────


@pytest.fixture()
def season_client():
    """시즌 경계를 사이에 둔 경기들. 26-27 개막일은 2026-11-01."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    db = TestingSession()
    db.add_all([
        models.Roster(no="7", name="홍길동", pos="FW", status="활동"),
        models.Roster(no="10", name="김철수", pos="MF", status="활동"),
    ])
    db.add_all([
        # ── 25-26 (경계 이전)
        models.Match(match_id=0, date="2025-08-10", goals="홍길동",
                     attendees="홍길동,김철수", mom="홍길동"),
        models.Match(match_id=1, date="2026-10-31", goals="홍길동",
                     attendees="홍길동,김철수", mom="김철수"),
        # ── 26-27 (개막일 당일부터)
        models.Match(match_id=2, date="2026-11-01", goals="김철수",
                     assists="홍길동", attendees="홍길동,김철수", mom="김철수"),
        # ── 날짜 없음: 어느 시즌에도 안 들어가지만 통산에는 남는다
        models.Match(match_id=3, date=None, goals="홍길동", attendees="홍길동"),
    ])
    db.commit()

    app.dependency_overrides[get_db] = lambda: TestingSession()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _by_name(client, url):
    return {r["name"]: r for r in client.get(url, headers=HEADERS).json()}


def test_season_param_splits_at_opening_day(season_client):
    """개막일 당일 경기부터 새 시즌이다."""
    s2526 = _by_name(season_client, "/api/underduck/stats?season=2526")
    assert s2526["홍길동"]["goals"] == 2      # 0·1번
    assert s2526["홍길동"]["apps"] == 2
    assert s2526["김철수"]["goals"] == 0

    s2627 = _by_name(season_client, "/api/underduck/stats?season=2627")
    assert s2627["김철수"]["goals"] == 1      # 2번만
    assert s2627["홍길동"]["goals"] == 0
    assert s2627["홍길동"]["assists"] == 1
    assert s2627["홍길동"]["apps"] == 1


def test_no_season_param_is_career_total(season_client):
    """season 을 안 주면 지금까지와 똑같이 전 기간을 센다.

    칭호의 통산 등급이 이 모드에 의존하므로 기본 동작이 바뀌면 안 된다.
    """
    career = _by_name(season_client, "/api/underduck/stats")
    # 득점은 0·1·3번 = 3골. 날짜 없는 3번도 통산에는 들어간다.
    assert career["홍길동"]["goals"] == 3
    # 출전은 네 경기 전부 — 2번은 골이 김철수일 뿐 홍길동도 명단에 있다.
    assert career["홍길동"]["apps"] == 4
    assert career["김철수"]["goals"] == 1


def test_undated_match_belongs_to_no_season(season_client):
    """날짜를 못 읽는 경기는 어느 시즌에도 안 들어간다.

    두 시즌 합이 통산보다 작아지지만, 날짜 없는 경기를 아무 시즌에나 밀어넣어
    엉뚱한 시즌 순위를 만드는 것보다 낫다.
    """
    s2526 = _by_name(season_client, "/api/underduck/stats?season=2526")
    s2627 = _by_name(season_client, "/api/underduck/stats?season=2627")
    career = _by_name(season_client, "/api/underduck/stats")
    assert s2526["홍길동"]["goals"] + s2627["홍길동"]["goals"] == 2
    assert career["홍길동"]["goals"] == 3


def test_unknown_season_id_is_rejected(season_client):
    """모르는 시즌 id 를 통산으로 떨어뜨리지 않는다.

    조용히 넘어가면 프론트가 시즌 화면에 통산 숫자를 띄우고도 아무도 모른다.
    프론트(app/lib/seasons.ts)와 백엔드 표가 어긋난 순간 여기서 터져야 한다.
    """
    r = season_client.get("/api/underduck/stats?season=9999", headers=HEADERS)
    assert r.status_code == 400
    assert "9999" in r.json()["detail"]


def test_season_filter_still_excludes_outings_and_upcoming(season_client):
    """시즌 필터를 걸어도 야유회·예정 제외 규칙은 그대로 살아있다."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    db.add_all([
        models.Roster(no="7", name="홍길동", pos="FW", status="활동"),
        models.Match(match_id=0, date="2026-11-02", type="야유회",
                     goals="바베큐", attendees="홍길동"),
        models.Match(match_id=1, date="2026-11-09", result="예정",
                     attendees="홍길동"),
        models.Match(match_id=2, date="2026-11-16", goals="홍길동",
                     attendees="홍길동"),
    ])
    db.commit()
    app.dependency_overrides[get_db] = lambda: TestingSession()

    by = _by_name(TestClient(app), "/api/underduck/stats?season=2627")
    assert "바베큐" not in by
    assert by["홍길동"]["apps"] == 1   # 2번만
    assert by["홍길동"]["goals"] == 1
