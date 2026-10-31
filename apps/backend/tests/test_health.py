def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_checks_database(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_readiness_reports_db_failure_without_leaking(client):
    from app.database import get_db
    from app.main import app

    class Broken:
        def execute(self, *_):
            raise RuntimeError("password=secret host=db")

    app.dependency_overrides[get_db] = lambda: Broken()
    try:
        r = client.get("/api/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert "secret" not in r.text


def test_cors_allows_only_frontend(client):
    ok = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options(
        "/api/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
