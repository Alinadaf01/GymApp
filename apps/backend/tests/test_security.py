"""Security regression tests: every route is authenticated unless explicitly public,
and production settings are strict."""
import re
import uuid

import pytest

from app.config import Settings

PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/health/ready"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/telegram/webhook"),  # authenticated by its own secret token
}


def all_routes() -> set[tuple[str, str]]:
    """Every (method, path) the app serves. Taken from the OpenAPI schema because
    included routers are not flattened into app.routes in this FastAPI version."""
    from app.main import app

    return {(m.upper(), path) for path, ops in app.openapi()["paths"].items() for m in ops}


def test_route_inventory_is_complete():
    routes = all_routes()
    assert PUBLIC <= routes
    assert len(routes) > 60  # guard: the inventory must not silently become empty


@pytest.mark.parametrize("method,path", sorted(all_routes() - PUBLIC))
def test_every_other_route_requires_login(client, method, path):
    url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
    r = client.request(method, url, headers={"X-Requested-With": "fetch"}, json={})
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


def test_webhook_without_secret_is_rejected(client):
    assert client.post("/api/telegram/webhook", json={}).status_code == 401


def test_production_cookie_and_docs():
    s = Settings(app_env="production", app_secret_key="x" * 40)
    assert s.cookie_secure is True
    assert s.session_cookie_name.startswith("__Host-")


def test_production_app_hides_docs(monkeypatch):
    from app import config, main

    prod = Settings(**PROD_OK)
    monkeypatch.setattr(config, "get_settings", lambda: prod)
    monkeypatch.setattr(main, "get_settings", lambda: prod)
    from fastapi.testclient import TestClient

    with TestClient(main.create_app()) as c:
        assert c.get("/api/docs").status_code == 404
        assert c.get("/api/openapi.json").status_code == 404
        r = c.options("/api/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
        assert "access-control-allow-origin" not in r.headers


PROD_OK = dict(app_env="production", app_secret_key="x" * 40,
               database_url="postgresql+psycopg://basharnia:Str0ng@db:5432/basharnia",
               frontend_url="https://coach.example.com")


def test_production_accepts_proper_settings():
    Settings(**PROD_OK).validate_for_production()


@pytest.mark.parametrize("override", [
    {"app_secret_key": "short"},
    {"database_url": "postgresql+psycopg://basharnia:devpass@localhost:5432/basharnia_dev"},
    {"frontend_url": "http://coach.example.com"},
])
def test_production_refuses_unsafe_settings(override):
    with pytest.raises(RuntimeError):
        Settings(**{**PROD_OK, **override}).validate_for_production()


def test_errors_do_not_leak_internals(client, admin):
    # unknown ids and malformed input return generic messages, never tracebacks/SQL
    from tests.conftest import PASSWORD
    client.post("/api/auth/login", json={"username": "coach", "password": PASSWORD},
                headers={"X-Requested-With": "fetch"})
    for url in (f"/api/students/{uuid.uuid4()}", "/api/students/not-a-uuid", f"/api/programs/{uuid.uuid4()}"):
        body = client.get(url).text.lower()
        assert "traceback" not in body and "sqlalchemy" not in body and "psycopg" not in body
