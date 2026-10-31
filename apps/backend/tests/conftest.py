"""Test setup: uses a dedicated test database (TEST_DATABASE_URL), never production."""
import os

import pytest

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://basharnia:devpass@localhost:5432/basharnia_test"
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("APP_ENV", "test")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pathlib import Path  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")


@pytest.fixture(autouse=True)
def clean_tables(migrated_db):
    """Each test starts from empty tables (API endpoints commit)."""
    from sqlalchemy import text

    from app.database import engine
    from app.database.base import Base

    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield


PASSWORD = "correct-horse-battery"


@pytest.fixture()
def admin():
    from app.auth.passwords import hash_password
    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as s:
        user = User(username="coach", password_hash=hash_password(PASSWORD))
        s.add(user)
        s.commit()
        return user


@pytest.fixture()
def auth_client(client, admin):
    r = client.post(
        "/api/auth/login",
        json={"username": "coach", "password": PASSWORD},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    client.headers["X-Requested-With"] = "fetch"
    return client


@pytest.fixture()
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
