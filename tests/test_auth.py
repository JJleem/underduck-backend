from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_authcheck_without_header_is_401():
    r = client.get("/api/underduck/_authcheck")
    assert r.status_code == 401


def test_authcheck_with_wrong_secret_is_401():
    r = client.get("/api/underduck/_authcheck", headers={"X-Underduck-Secret": "nope"})
    assert r.status_code == 401


def test_authcheck_with_correct_secret_is_200():
    r = client.get("/api/underduck/_authcheck", headers={"X-Underduck-Secret": "test-secret"})
    assert r.status_code == 200
    assert r.json() == {"authed": True}
