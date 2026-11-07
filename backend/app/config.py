"""Application settings, loaded from environment variables / backend/.env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'aitutor.db').as_posix()}"

    # Auth
    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    ip_max_failures: int = 20
    reset_token_minutes: int = 30
    verify_token_hours: int = 48

    # Keys (kept apart from the database and the backups)
    keyring_path: str = "./keys/keyring.json"

    # AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    ai_mode: str = "auto"  # auto | offline
    # tried in order if the main model is overloaded (comma-separated)
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-flash-lite-latest,gemini-3.5-flash"
    gemini_retries: int = 2  # retries per model for 429/5xx (exponential back-off / Gemini's retry hint)
    gemini_rpm: int = 12  # free-tier protection: max requests per minute across the whole app (0 = no limit)
    gemini_concurrency: int = 3  # parallel AI calls for batch jobs (question drafting, curriculum chunks)
    gemini_background_timeout_seconds: float = 180.0  # budget per call for background jobs (waits out rate limits)
    curriculum_part_chars: int = 4500  # curriculum text is read in parts of about this size (any layout)
    gemini_retry_base_seconds: float = 1.0
    gemini_request_timeout_seconds: float = 30.0  # one HTTP call
    gemini_total_timeout_seconds: float = 45.0  # all retries + backups for one request
    gemini_cooldown_seconds: float = 120.0  # skip an overloaded model for this long

    # Automation: curriculum approval (when the extraction has no errors), CLO-PLO mappings, course activation,
    # lessons and personalised lectures per student happen without waiting for a teacher. Assessment questions are
    # drafted by the AI but ALWAYS need a teacher's approval; the diagnostic goes live once enough are approved.
    # Everything stays traced and in the review queue. AUTOMATION=false = a teacher approves each step instead.
    automation: bool = True

    # Onboarding
    allowed_email_domain: str = "university.edu"
    consent_version: str = "2026-1"
    frontend_url: str = "https://localhost:5173"

    # Storage
    upload_dir: str = "./data/uploads"
    outbox_dir: str = "./outbox"
    backup_dir: str = "./backups"
    max_upload_mb: int = 20

    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @property
    def db_url(self) -> str:
        """SQLite paths are resolved relative to the backend folder, not the current directory."""
        u = self.database_url
        if u.startswith("sqlite:///") and not u.startswith("sqlite:////") and not Path(u[10:]).is_absolute():
            return "sqlite:///" + (BACKEND_DIR / u[10:]).resolve().as_posix()
        return u

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
