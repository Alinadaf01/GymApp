"""Application settings, read only from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development")
    app_secret_key: str = Field(default="")
    database_url: str = Field(default="postgresql+psycopg://basharnia:devpass@localhost:5432/basharnia_dev")
    frontend_url: str = Field(default="http://localhost:3000")
    api_base_url: str = Field(default="http://localhost:8000")

    admin_username: str = Field(default="")
    initial_admin_password: str = Field(default="")

    telegram_bot_token: str = Field(default="")
    telegram_allowed_user_id: int | None = Field(default=None)
    telegram_webhook_secret: str = Field(default="")

    whisper_model: str = Field(default="small")
    whisper_device: str = Field(default="cpu")
    whisper_compute_type: str = Field(default="int8")
    audio_max_duration_seconds: int = Field(default=900)

    storage_root: Path = Field(default=Path("./data"))
    max_upload_mb: int = Field(default=20)

    timezone: str = Field(default="Asia/Tehran")

    session_ttl_hours: int = Field(default=168)  # 7 days
    login_max_failures_per_user: int = Field(default=5)
    login_max_failures_per_ip: int = Field(default=20)
    login_window_minutes: int = Field(default=15)

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @property
    def session_cookie_name(self) -> str:
        # __Host- prefix: browser enforces Secure, Path=/ and no Domain (production only)
        return "__Host-basharnia_session" if self.cookie_secure else "basharnia_session"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_for_production(self) -> None:
        """Fail fast if required secrets are missing in production."""
        if not self.is_production:
            return
        missing = [
            name
            for name, value in {
                "APP_SECRET_KEY": self.app_secret_key,
                "DATABASE_URL": self.database_url,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
        if len(self.app_secret_key) < 32:
            raise RuntimeError("APP_SECRET_KEY must be at least 32 characters in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
