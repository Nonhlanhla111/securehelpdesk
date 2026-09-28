"""Application settings, loaded from environment variables / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_KEY = "dev-only-insecure-key-do-not-use-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SecureHelpDesk"
    environment: str = "development"  # development | production

    database_url: str = "sqlite:///./securehelpdesk.db"

    secret_key: str = _INSECURE_DEFAULT_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Brute-force protection
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    login_rate_limit: int = 10          # attempts per window, per IP
    login_rate_window_seconds: int = 60
    register_rate_limit: int = 5
    register_rate_window_seconds: int = 3600

    # File uploads
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 5 * 1024 * 1024

    cors_origins: list[str] = ["http://localhost:5173"]

    # Optional: if all three are set and no user with this email exists yet,
    # the app creates an Administrator account on startup. Meant for hosts
    # with no interactive terminal (e.g. Render) where `create_admin` can't
    # be run by hand. Leave unset for local development.
    admin_bootstrap_email: str | None = None
    admin_bootstrap_name: str | None = None
    admin_bootstrap_password: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.secret_key == _INSECURE_DEFAULT_KEY:
        raise RuntimeError("SECRET_KEY must be set to a strong random value in production.")
    return s
