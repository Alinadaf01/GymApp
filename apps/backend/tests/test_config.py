import pytest

from app.config import Settings


def test_production_requires_strong_secret():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", app_secret_key="").validate_for_production()
    with pytest.raises(RuntimeError):
        Settings(app_env="production", app_secret_key="short").validate_for_production()
    Settings(app_env="production", app_secret_key="x" * 40, database_url="postgresql+psycopg://u:p@db/x",
             frontend_url="https://coach.example.com").validate_for_production()


def test_development_does_not_require_secret():
    Settings(app_env="development", app_secret_key="").validate_for_production()
