"""App-wide settings loaded from .env using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """All environment variables used by the application.

    Loaded from .env file automatically. Required vars will cause a clear
    error at startup if missing.
    """

    # API connection (pipeline writes to DB via FastAPI)
    api_base_url: str = "http://localhost:8000"
    api_secret_key: str = ""

    # LLM
    openai_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id_urgent: str = ""
    telegram_chat_id_digest: str = ""
    telegram_chat_id_review: str = ""

    # Email finders
    apollo_api_key: str = ""
    snov_user_id: str = ""
    snov_api_secret: str = ""
    hunter_api_key: str = ""

    # Gmail SMTP
    gmail_address: str = ""
    gmail_app_password: str = ""

    # Job board accounts (expendable)
    naukri_email: str = ""
    naukri_password: str = ""
    indeed_email: str = ""
    indeed_password: str = ""
    foundit_email: str = ""
    foundit_password: str = ""

    # Aggregator APIs
    jooble_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    rapidapi_key: str = ""
    themuse_api_key: str = ""
    findwork_token: str = ""

    # Langfuse (prompt management + tracing)
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # App settings
    profile_id: int | None = None  # DB profile ID (overrides profile_path if set)
    profile_path: str = "config/profiles/ravi_raj.yaml"
    dry_run: bool = True
    log_level: str = "INFO"

    # Email system modes
    email_sending_enabled: bool = False
    email_verification_enabled: bool = True
    cold_email_delay_seconds: int = 5
    cold_email_max_per_hour: int = 8
    cold_email_max_per_day: int = 12

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


def load_settings() -> AppSettings:
    """Load and return application settings from environment/.env file."""
    return AppSettings()
