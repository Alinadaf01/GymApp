from datetime import timedelta

from sqlalchemy import select

from app.auth.sessions import now_utc
from app.config import get_settings
from app.database import SessionLocal
from app.models import ActivityLog, AuthSession, LoginAttempt
from tests.conftest import PASSWORD

H = {"X-Requested-With": "fetch"}
COOKIE = get_settings().session_cookie_name


def login(client, username="coach", password=PASSWORD, headers=H):
    return client.post("/api/auth/login", json={"username": username, "password": password}, headers=headers)


def test_login_success_sets_httponly_cookie(client, admin):
    r = login(client)
    assert r.status_code == 200
    assert r.json()["username"] == "coach"
    set_cookie = r.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in set_cookie
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/" in set_cookie
    # token is not returned in the body
    assert "token" not in r.text


def test_session_token_stored_hashed(client, admin):
    login(client)
    token = client.cookies.get(COOKIE)
    with SessionLocal() as s:
        stored = s.scalar(select(AuthSession.token_hash))
    assert stored and stored != token and len(stored) == 64


def test_username_is_case_insensitive(client, admin):
    assert login(client, username="  Coach ").status_code == 200


def test_wrong_password_and_unknown_user_give_same_error(client, admin):
    a = login(client, password="wrong-password")
    b = login(client, username="nobody")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_session(auth_client):
    r = auth_client.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["username"] == "coach"


def test_logout_revokes_session_server_side(auth_client):
    token = auth_client.cookies.get(COOKIE)
    assert auth_client.post("/api/auth/logout").status_code == 204
    # Even replaying the old cookie must fail
    auth_client.cookies.set(COOKIE, token)
    assert auth_client.get("/api/auth/me").status_code == 401


def test_expired_session_rejected(auth_client):
    with SessionLocal() as s:
        sess = s.scalar(select(AuthSession))
        sess.expires_at = now_utc() - timedelta(seconds=1)
        s.commit()
    assert auth_client.get("/api/auth/me").status_code == 401


def test_inactive_user_rejected(auth_client, admin):
    from app.models import User

    with SessionLocal() as s:
        s.get(User, admin.id).is_active = False
        s.commit()
    assert auth_client.get("/api/auth/me").status_code == 401


def test_rate_limit_per_username(client, admin):
    limit = get_settings().login_max_failures_per_user
    for _ in range(limit):
        assert login(client, password="bad-password").status_code == 401
    # Even the correct password is blocked while limited
    r = login(client)
    assert r.status_code == 429
    with SessionLocal() as s:
        assert len(s.scalars(select(LoginAttempt)).all()) == limit


def test_successful_login_clears_failures(client, admin):
    login(client, password="bad-password")
    assert login(client).status_code == 200
    with SessionLocal() as s:
        assert s.scalars(select(LoginAttempt)).all() == []


def test_csrf_header_required_for_mutations(client, admin):
    r = login(client, headers={})
    assert r.status_code == 403


def test_csrf_foreign_origin_rejected(client, admin):
    r = login(client, headers={**H, "Origin": "https://evil.example"})
    assert r.status_code == 403
    r = login(client, headers={**H, "Origin": get_settings().frontend_url})
    assert r.status_code == 200


def test_change_password(auth_client, client):
    new = "a-brand-new-password"
    r = auth_client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": new})
    assert r.status_code == 204
    # current session survives
    assert auth_client.get("/api/auth/me").status_code == 200
    with SessionLocal() as s:
        assert s.scalar(select(ActivityLog.action)) == "auth.password_changed"
    auth_client.cookies.clear()
    assert login(auth_client).status_code == 401
    assert login(auth_client, password=new).status_code == 200


def test_change_password_revokes_other_sessions(auth_client, admin):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as other:
        assert login(other).status_code == 200
        auth_client.post(
            "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "another-good-pass"}
        )
        assert other.get("/api/auth/me").status_code == 401


def test_change_password_validation(auth_client):
    r = auth_client.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": "x" * 20})
    assert r.status_code == 400
    r = auth_client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 422
    r = auth_client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert r.status_code == 422


def test_password_hash_is_argon2id(admin):
    assert admin.password_hash.startswith("$argon2id$")
