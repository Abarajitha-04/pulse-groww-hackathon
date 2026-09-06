"""
Central configuration. Reads from environment variables (see .env.example).

Design decision: SQLite is the default DATABASE_URL so the project runs
with zero external setup during a 72-hour build / a judge's clean clone.
Swapping to Postgres for production is a one-line env var change because
all access goes through SQLAlchemy's engine, not raw SQLite calls.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Pulse"
    DATABASE_URL: str = "sqlite:///./pulse.db"
    SECRET_KEY: str = "change-me-in-production-this-is-a-hackathon-default"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days, fine for a demo

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Polling / significance tuning
    POLL_INTERVAL_SECONDS: int = 45
    SIGNIFICANCE_Z_THRESHOLD: float = 1.5
    MIN_HISTORY_POINTS: int = 8
    STALENESS_SECONDS: int = 90

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


settings = Settings()
