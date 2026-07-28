"""전 도메인 통합 테스트: 앱 전체를 SQLite in-memory로 띄워 실제 HTTP로 CRUD 검증.

get_db 만 SQLite 세션으로 오버라이드한다(인증/라우팅/스키마/비즈니스로직은 실제 코드 경로).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.connection import Base, get_db
from main import app

H = {"X-Underduck-Secret": "test-secret"}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app.dependency_overrides[get_db] = lambda: TestingSession()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_match(client):
    r = client.post("/api/underduck/matches", headers=H, json={
        "date": "2026-06-01", "time": "10:00", "location": "구장",
        "opponent": "상대팀", "type": "리그",
    })
    assert r.status_code == 201, r.text
    return r.json()["match_id"]


def test_auth_blocks_every_domain(client):
    # 헤더 없으면 전부 차단. 같은 IP에서 실패가 쌓이면 401 → 429(브루트포스 스로틀)로 바뀐다.
    for path in ["/matches", "/mom-vote", "/vote-comment", "/attendance",
                 "/featured", "/push", "/roster", "/stats", "/notice",
                 "/lineup", "/feedback", "/users", "/media"]:
        assert client.get(f"/api/underduck{path}").status_code in (401, 429), path


def test_matches_crud_and_photos(client):
    mid = _make_match(client)
    assert mid == 0  # 첫 경기 = 0-based

    r = client.patch(f"/api/underduck/matches/{mid}", headers=H, json={
        "our_score": 3, "their_score": 1, "result": "승",
        "goals": "홍길동,홍길동,김철수", "assists": "박영희,,", "mom": "홍길동",
    })
    assert r.status_code == 200 and r.json()["our_score"] == 3

    # 사진 추가/중복무시/삭제
    client.post(f"/api/underduck/matches/{mid}/photos", headers=H,
                json={"urls": ["a.jpg", "a.jpg", "b.jpg"]})
    r = client.get(f"/api/underduck/matches/{mid}", headers=H)
    assert r.json()["photos"] == "a.jpg,b.jpg"
    r = client.request("DELETE", f"/api/underduck/matches/{mid}/photos",
                       headers=H, json={"url": "a.jpg"})
    assert r.json()["photos"] == "b.jpg"

    # 최대 5장 초과 거부
    over = client.post(f"/api/underduck/matches/{mid}/photos", headers=H,
                       json={"urls": ["c", "d", "e", "f", "g"]})
    assert over.status_code == 400

    assert client.get("/api/underduck/matches/999", headers=H).status_code == 404


def test_roster(client):
    r = client.post("/api/underduck/roster", headers=H, json={
        "no": "7", "name": "홍길동", "pos": "FW", "status": "활동"})
    assert r.status_code == 201
    assert len(client.get("/api/underduck/roster", headers=H).json()) == 1


def test_attendance_finalize(client):
    mid = _make_match(client)
    client.post("/api/underduck/attendance", headers=H, json={
        "match_id": mid, "kakao_id": "k1", "nickname": "홍길동", "response": "참석"})
    # upsert: 같은 (match,kakao) 다시 → 갱신
    client.post("/api/underduck/attendance", headers=H, json={
        "match_id": mid, "kakao_id": "k1", "nickname": "홍길동", "response": "불참"})
    client.post("/api/underduck/attendance", headers=H, json={
        "match_id": mid, "kakao_id": "k2", "nickname": "김철수", "response": "참석"})
    rows = client.get(f"/api/underduck/attendance?match_id={mid}", headers=H).json()
    assert len(rows) == 2  # k1은 upsert로 1건 유지

    fin = client.post(f"/api/underduck/attendance/{mid}/finalize", headers=H).json()
    assert fin["attendees"] == "김철수"  # 참석자만
    m = client.get(f"/api/underduck/matches/{mid}", headers=H).json()
    assert m["attendance_status"] == "마감" and m["attendees"] == "김철수"

    st = client.patch(f"/api/underduck/attendance/{mid}/status", headers=H,
                      json={"status": "진행중"})
    assert st.json()["attendance_status"] == "진행중"


def test_mom_vote(client):
    client.post("/api/underduck/mom-vote", headers=H, json={
        "match_id": 0, "voter_name": "a", "voted_for": "홍길동", "vote_type": "공격"})
    client.post("/api/underduck/mom-vote", headers=H, json={
        "match_id": 0, "voter_name": "a", "voted_for": "박영희", "vote_type": "수비"})
    assert len(client.get("/api/underduck/mom-vote?match_id=0", headers=H).json()) == 2
    # vote_type 지정 삭제
    d = client.request("DELETE", "/api/underduck/mom-vote", headers=H,
                       json={"match_id": 0, "voter_name": "a", "vote_type": "공격"})
    assert d.json()["deleted"] == 1
    assert len(client.get("/api/underduck/mom-vote", headers=H).json()) == 1


def test_vote_comment(client):
    r = client.post("/api/underduck/vote-comment", headers=H, json={
        "match_id": 0, "kakao_id": "k1", "nickname": "홍", "message": "굿"})
    cid = r.json()["id"]
    assert client.get("/api/underduck/vote-comment", headers=H).json()[0]["message"] == "굿"
    assert client.delete(f"/api/underduck/vote-comment/{cid}", headers=H).json()["deleted"] == 1


def test_featured(client):
    r = client.put("/api/underduck/featured", headers=H, json={
        "player_name": "홍길동", "title_ids": ["t1", "t2"]})
    assert r.json()["title_id1"] == "t1" and r.json()["title_id3"] is None
    # 같은 선수 갱신
    client.put("/api/underduck/featured", headers=H, json={
        "player_name": "홍길동", "title_ids": ["x"]})
    rows = client.get("/api/underduck/featured", headers=H).json()
    assert len(rows) == 1 and rows[0]["title_id1"] == "x"


def test_push(client):
    client.post("/api/underduck/push", headers=H, json={
        "endpoint": "https://e1", "p256dh": "p", "auth": "a"})
    client.post("/api/underduck/push", headers=H, json={  # 같은 endpoint upsert
        "endpoint": "https://e1", "p256dh": "p2", "auth": "a2"})
    rows = client.get("/api/underduck/push", headers=H).json()
    assert len(rows) == 1 and rows[0]["p256dh"] == "p2"
    assert client.request("DELETE", "/api/underduck/push", headers=H,
                          json={"endpoint": "https://e1"}).json()["deleted"] == 1


def test_notice(client):
    assert client.get("/api/underduck/notice", headers=H).json() is None
    client.put("/api/underduck/notice", headers=H, json={
        "date": "2026-06-01", "title": "공지", "content": "내용", "important": True})
    n = client.get("/api/underduck/notice", headers=H).json()
    assert n["title"] == "공지" and n["important"] is True
    # 단일행 갱신(새 row 안 생김)
    client.put("/api/underduck/notice", headers=H, json={
        "date": "2026-06-02", "title": "공지2", "content": "c", "important": False})
    assert client.get("/api/underduck/notice", headers=H).json()["title"] == "공지2"


def test_lineup_upsert_and_delete(client):
    body = {"match_id": 0, "quarter": "1Q", "formation": "4-4-2",
            "players": ["p%d" % i for i in range(11)], "subs": ["s1"],
            "substitutions": [{"out": "p1", "in": "s1", "time": "60"}]}
    client.put("/api/underduck/lineup", headers=H, json=body)
    rows = client.get("/api/underduck/lineup?match_id=0", headers=H).json()
    assert len(rows) == 1 and rows[0]["formation"] == "4-4-2"
    assert rows[0]["substitutions"][0]["in"] == "s1"
    # 빈 라인업 → 삭제 시맨틱
    empty = {"match_id": 0, "quarter": "1Q", "formation": "", "players": [],
             "subs": [], "substitutions": []}
    assert client.put("/api/underduck/lineup", headers=H, json=empty).json()["deleted"] is True
    assert client.get("/api/underduck/lineup?match_id=0", headers=H).json() == []


def test_lineup_positions_and_tactic(client):
    base = {"match_id": 0, "quarter": "1Q", "formation": "4-4-2",
            "players": ["p%d" % i for i in range(11)], "subs": [], "substitutions": []}

    # 좌표·전술 미지정 → NULL (기존 라인업 하위호환)
    client.put("/api/underduck/lineup", headers=H, json=base)
    row = client.get("/api/underduck/lineup?match_id=0", headers=H).json()[0]
    assert row["positions"] is None and row["tactic"] is None

    # 자유 배치 좌표 + 팀 전술 + 개인 전술 저장
    pos = [[50.0, 88.0]] + [[10.0 * i, 40.0] for i in range(10)]
    ins = ["hold_line"] + ["join_attack,press_high"] * 5 + [""] * 5
    client.put("/api/underduck/lineup", headers=H,
               json={**base, "positions": pos, "tactic": "counter", "instructions": ins})
    row = client.get("/api/underduck/lineup?match_id=0", headers=H).json()[0]
    assert row["positions"] == pos and row["tactic"] == "counter"
    assert row["instructions"] == ins

    # 범위 밖 좌표 / 11개 초과 / 잘못된 쌍은 거부
    assert client.put("/api/underduck/lineup", headers=H,
                      json={**base, "positions": [[50, 120]]}).status_code == 422
    assert client.put("/api/underduck/lineup", headers=H,
                      json={**base, "positions": [[50, 50]] * 12}).status_code == 422
    assert client.put("/api/underduck/lineup", headers=H,
                      json={**base, "positions": [[50]]}).status_code == 422


def test_feedback(client):
    r = client.post("/api/underduck/feedback", headers=H, json={
        "match_id": 0, "name": "홍", "message": "수고"})
    fid = r.json()["id"]
    assert client.get("/api/underduck/feedback", headers=H).json()[0]["message"] == "수고"
    assert client.delete(f"/api/underduck/feedback/{fid}", headers=H).json()["deleted"] == 1
    assert client.delete("/api/underduck/feedback/999", headers=H).status_code == 404


def test_users(client):
    client.post("/api/underduck/users", headers=H, json={
        "kakao_id": "k1", "nickname": "홍", "profile_image": "img"})
    # upsert: last_login 갱신, 중복 생성 없음
    client.post("/api/underduck/users", headers=H, json={
        "kakao_id": "k1", "nickname": "길동", "profile_image": "img2"})
    assert len(client.get("/api/underduck/users", headers=H).json()) == 1
    assert client.get("/api/underduck/users/k1", headers=H).json()["nickname"] == "길동"
    assert client.get("/api/underduck/users/none", headers=H).status_code == 404


def test_media(client):
    r = client.post("/api/underduck/media", headers=H, json={
        "type": "image", "url": "https://u1", "title": "t"})
    mid = r.json()["id"]
    assert len(client.get("/api/underduck/media", headers=H).json()) == 1
    assert client.delete(f"/api/underduck/media/{mid}", headers=H).json()["deleted"] == 1


def test_stats_smoke(client):
    # 빈 DB → 빈 리스트, 200
    r = client.get("/api/underduck/stats", headers=H)
    assert r.status_code == 200 and r.json() == []


# ── 권한 검사 (실제 HTTP 경로) ──────────────────────────────────────
# 핵심: 신원 헤더가 없으면 기존과 동일, 있으면 소유자/관리자만 통과.

def _make_post(client, kakao_id="owner-1", headers=None):
    r = client.post("/api/underduck/board", headers=headers or H, json={
        "kakao_id": kakao_id, "author": "작성자", "title": "제목",
        "youtube_url": "https://youtu.be/abc",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _quarter(q="1Q", tactic="press"):
    return {
        "quarter": q,
        "formation": "4-3-3",
        "positions": [[50.0, 88.0]] + [[10.0 * i, 40.0] for i in range(10)],
        "players": ["p%d" % i for i in range(11)],
        "instructions": ["", "overlap,press"] + [""] * 9,
        "tactic": tactic,
    }


def test_board_lineup_post_is_one_per_author(client):
    lineup = {"quarters": [_quarter("1Q"), _quarter("2Q", "counter")]}
    body = {"kakao_id": "coach-1", "author": "감독", "title": "내 전술", "lineup": lineup}

    r = client.post("/api/underduck/board", headers=H, json=body)
    assert r.status_code == 201
    pid = r.json()["id"]
    quarters = r.json()["lineup"]["quarters"]
    assert [q["quarter"] for q in quarters] == ["1Q", "2Q"]
    assert quarters[1]["tactic"] == "counter"
    assert r.json()["updated_at"] is None  # 최초 작성은 수정 표시 없음

    # 같은 작성자가 다시 올리면 새 글이 아니라 기존 글이 갱신된다
    again = client.post("/api/underduck/board", headers=H, json={
        **body, "title": "내 전술 v2", "lineup": {"quarters": [_quarter("3Q", "attack")]}})
    assert again.json()["id"] == pid
    assert again.json()["title"] == "내 전술 v2"
    assert [q["quarter"] for q in again.json()["lineup"]["quarters"]] == ["3Q"]
    assert again.json()["updated_at"] is not None  # 수정됨 표시

    # 빈 쿼터 목록은 거부 — 옛 구조 payload가 라인업을 비워버리는 사고 방지
    assert client.post("/api/underduck/board", headers=H, json={
        **body, "lineup": {"quarters": []}}).status_code == 422
    assert client.post("/api/underduck/board", headers=H, json={
        **body, "lineup": {"formation": "4-3-3", "players": []}}).status_code == 422

    # 쿼터는 최대 4개
    over = client.post("/api/underduck/board", headers=H, json={
        **body, "lineup": {"quarters": [_quarter("%dQ" % i) for i in range(1, 6)]}})
    assert over.status_code == 422

    # 다른 작성자는 자기 글을 따로 가진다
    other = client.post("/api/underduck/board", headers=H, json={
        **body, "kakao_id": "coach-2", "title": "다른 전술"})
    assert other.json()["id"] != pid

    posts = client.get("/api/underduck/board", headers=H).json()
    assert len([p for p in posts if p["lineup"]]) == 2

    # 유튜브 글은 lineup 없이 그대로 동작
    yt = client.post("/api/underduck/board", headers=H, json={
        "kakao_id": "coach-1", "author": "감독", "title": "영상",
        "youtube_url": "https://youtu.be/abc"})
    assert yt.status_code == 201 and yt.json()["lineup"] is None


def test_board_delete_unchanged_without_identity_header(client):
    """레거시(헤더 없음): 지금까지처럼 그냥 삭제된다 → 프론트 컷오버 전 기능 영향 없음."""
    pid = _make_post(client)
    r = client.delete(f"/api/underduck/board/{pid}", headers=H)
    assert r.status_code == 200 and r.json() == {"deleted": 1}


def test_board_delete_blocked_for_non_author(client):
    pid = _make_post(client)
    r = client.delete(f"/api/underduck/board/{pid}", headers={
        **H, "X-Underduck-User": "someone-else", "X-Underduck-Role": "member"})
    assert r.status_code == 403
    # 글은 그대로 남아 있어야 한다
    assert client.get(f"/api/underduck/board/{pid}", headers=H).status_code == 200


def test_board_delete_allowed_for_author_and_admin(client):
    pid = _make_post(client)
    assert client.delete(f"/api/underduck/board/{pid}", headers={
        **H, "X-Underduck-User": "owner-1", "X-Underduck-Role": "member"}).status_code == 200

    pid2 = _make_post(client)
    assert client.delete(f"/api/underduck/board/{pid2}", headers={
        **H, "X-Underduck-User": "admin-9", "X-Underduck-Role": "admin"}).status_code == 200


def test_body_kakao_id_cannot_spoof_identity(client):
    """본문에 남의 kakao_id를 넣어도 헤더 신원으로 덮어써 저장된다(가명값으로)."""
    import security

    post_id = _make_post(client, kakao_id="victim", headers={
        **H, "X-Underduck-User": "attacker", "X-Underduck-Role": "member"})
    stored = client.get(f"/api/underduck/board/{post_id}", headers=H).json()["kakao_id"]
    assert stored == security.pseudonymize("attacker")
    assert stored != security.pseudonymize("victim")
    # 원본 카카오 ID는 응답 어디에도 남지 않는다
    assert "victim" not in stored and "attacker" not in stored


def test_admin_only_endpoints_reject_member(client):
    mid = _make_match(client)  # 레거시 헤더 → 기존대로 생성됨
    member = {**H, "X-Underduck-User": "u1", "X-Underduck-Role": "member"}
    assert client.patch(f"/api/underduck/matches/{mid}", headers=member,
                        json={"our_score": 9}).status_code == 403
    assert client.post("/api/underduck/roster", headers=member, json={
        "no": "7", "name": "홍길동", "pos": "MF", "status": "활동"}).status_code == 403
    assert client.post(f"/api/underduck/attendance/{mid}/finalize",
                       headers=member).status_code == 403


def test_xss_url_rejected_over_http(client):
    r = client.post("/api/underduck/board", headers=H, json={
        "kakao_id": "u1", "author": "가", "title": "t",
        "youtube_url": "javascript:alert(document.cookie)"})
    assert r.status_code == 422


def test_mom_vote_is_one_per_voter_and_type(client):
    """같은 (경기, 투표자, 부문)에 재투표하면 쌓이지 않고 갈아끼워진다."""
    def vote(voted_for):
        return client.post("/api/underduck/mom-vote", headers=H, json={
            "match_id": 0, "voter_name": "홍길동", "voted_for": voted_for, "vote_type": "공격"})

    vote("김철수")
    vote("박영희")   # 프론트의 DELETE 없이 바로 재투표 = 직접 API 호출 시나리오
    vote("이민수")

    rows = client.get("/api/underduck/mom-vote?match_id=0", headers=H).json()
    assert len(rows) == 1, "표가 쌓였다 — 표 조작이 가능하다"
    assert rows[0]["voted_for"] == "이민수", "마지막 표가 남아야 한다"

    # 다른 부문은 별개로 유지된다
    client.post("/api/underduck/mom-vote", headers=H, json={
        "match_id": 0, "voter_name": "홍길동", "voted_for": "김철수", "vote_type": "수비"})
    assert len(client.get("/api/underduck/mom-vote?match_id=0", headers=H).json()) == 2


def test_raw_kakao_id_never_travels_in_a_url(client):
    """원본 카카오 ID를 URL에 실어 pid를 얻는 경로가 없어야 한다.

    nginx access log는 쿼리스트링·경로를 그대로 기록한다. GET으로 변환이 되면
    로그인할 때마다 원본 ID가 서버 로그에 평문으로 쌓여, DB에서 없앤 의미가 사라진다.
    """
    import security

    pid = security.pseudonymize("3812457")

    # 정상 경로: POST 본문 (본문은 access log에 안 남는다)
    r = client.post("/api/underduck/users/resolve", headers=H, json={"kakao_id": "3812457"})
    assert r.status_code == 200 and r.json() == {"kakao_id": pid}

    # URL로는 변환되지 않는다 (/users/{kakao_id} 로 흘러가 404)
    r = client.get("/api/underduck/users/resolve?kakao_id=3812457", headers=H)
    assert r.status_code != 200 and pid not in r.text
