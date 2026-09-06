"""
Central configuration. Reads from environment variables (see .env.example).

Design decision: SQLite is the default DATABASE_URL so the project runs
with zero external setup during local dev / a clean clone. Swapping to
Postgres for production is a one-line env var change because all access
goes through SQLAlchemy's engine, not raw SQLite calls (see alembic/ for
the migration path).

ENVIRONMENT gates a small number of production-only safety checks (see
main.py's startup validation): it refuses to boot with the default
SECRET_KEY, a wildcard-ish CORS list, or SQLite when ENVIRONMENT=production,
rather than silently running insecurely. Nothing else in the app branches
on this value — it exists purely as a guardrail, not a feature flag.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Pulse"
    ENVIRONMENT: str = "development"  # "development" | "production"

    DATABASE_URL: str = "sqlite:///./pulse.db"
    SECRET_KEY: str = "change-me-in-production-this-is-a-hackathon-default"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Cache backend: "memory" (single-process, dev default) or "redis"
    # (required once you run more than one backend instance — see
    # app/services/cache.py and docs/DECISIONS.md).
    CACHE_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"

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

    # Rate limiting (slowapi). A single string like "5/minute".
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_DEFAULT: str = "120/minute"

    # Email (SMTP) — used for password reset and significant-move alerts.
    # Left unset by default: notification_service.py logs instead of
    # sending when SMTP isn't configured, so the app runs without an
    # email provider until you actually have one.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "Pulse <noreply@pulse.app>"
    SMTP_USE_TLS: bool = True

    # Optional error tracking. Unset = disabled.
    SENTRY_DSN: str | None = None

    # Market data provider: "auto" (yfinance + NSE fallback, the default,
    # free-tier dev/demo path) or "groww" (Groww's own Trading API, once
    # you have an account + subscription) — see
    # app/services/market_data/README.md for the trade-offs.
    MARKET_DATA_PROVIDER: str = "auto"
    GROWW_API_KEY: str | None = None
    GROWW_API_SECRET: str | None = None

    FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()
