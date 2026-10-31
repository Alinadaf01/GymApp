import pytest
from sqlalchemy import select

from app import cli
from app.auth.passwords import verify_password
from app.database import SessionLocal
from app.models import User


def test_create_admin_from_env(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "Coach")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "a-strong-password")
    cli.main(["create-admin"])
    with SessionLocal() as s:
        user = s.scalar(select(User))
    assert user.username == "coach"
    assert verify_password(user.password_hash, "a-strong-password")


def test_create_admin_only_once(monkeypatch, admin):
    monkeypatch.setenv("ADMIN_USERNAME", "second")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "a-strong-password")
    with pytest.raises(SystemExit):
        cli.main(["create-admin"])


def test_create_admin_rejects_weak_password(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "coach")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "123")
    with pytest.raises(SystemExit):
        cli.main(["create-admin"])
    with SessionLocal() as s:
        assert s.scalar(select(User)) is None


def test_reset_password(monkeypatch, admin):
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "recovered-password")
    cli.main(["reset-password"])
    with SessionLocal() as s:
        assert verify_password(s.scalar(select(User)).password_hash, "recovered-password")
