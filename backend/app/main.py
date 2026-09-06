import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth, watchlists, market, users, chat
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging_config import configure_logging, request_id_var
from app.db.session import Base, engine
from app.services import cache
from app.services.scheduler import start_scheduler, set_main_loop
from app.ws import prices

configure_logging()
logger = logging.getLogger("pulse.main")

if settings.SENTRY_DSN:
    # Optional and lazy: sentry-sdk is only imported when a DSN is actually
    # configured, so it never becomes a hard boot-time dependency for
    # anyone who hasn't set one up yet.
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[FastApiIntegration(), LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
        traces_sample_rate=0.1,
    )
    logger.info("Sentry error tracking enabled")

# In development, create_all() gives zero-setup boot (clone + run, no
# migration step). In production, Alembic (alembic/, run via
# `alembic upgrade head` as a deploy step — see docs/DEPLOYMENT.md) is the
# single source of truth for schema changes; letting create_all() also
# run there would let the app silently paper over a missed migration.
if settings.ENVIRONMENT != "production":
    Base.metadata.create_all(bind=engine)


def _validate_production_config() -> None:
    """Refuse to boot with an insecure default in production, rather than
    silently running that way. This is intentionally narrow — it checks
    the handful of settings that would otherwise fail *open* (a known
    secret key, a database that resets every deploy, no restriction on
    who can call the API) — not a general lint pass."""
    if settings.ENVIRONMENT != "production":
        return

    problems = []
    if settings.SECRET_KEY == "change-me-in-production-this-is-a-hackathon-default":
        problems.append("SECRET_KEY is still the default value")
    if len(settings.SECRET_KEY) < 32:
        problems.append("SECRET_KEY is too short (use at least 32 random bytes)")
    if settings.DATABASE_URL.startswith("sqlite"):
        problems.append("DATABASE_URL is SQLite (use Postgres in production — see alembic/)")
    if any(origin in ("*", "http://localhost:5173") for origin in settings.CORS_ORIGINS):
        problems.append("CORS_ORIGINS still includes a dev/wildcard origin")
    if settings.CACHE_BACKEND == "memory":
        problems.append("CACHE_BACKEND is 'memory' (won't work correctly with >1 backend instance)")

    if problems:
        raise RuntimeError(
            "Refusing to start with ENVIRONMENT=production and insecure config:\n  - "
            + "\n  - ".join(problems)
        )


_validate_production_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    set_main_loop(loop)
    cache.broadcaster.set_loop(loop)
    start_scheduler()
    yield
    # No explicit shutdown step today: APScheduler's BackgroundScheduler
    # runs daemon threads that die with the process, and the Redis
    # subscriber thread (app/services/cache.py) is daemonized the same
    # way — nothing here currently holds a resource that needs a clean
    # close on shutdown.


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Assigns a request ID (or reuses a client/proxy-supplied one),
    stores it in a contextvar so every log line emitted while handling
    this request carries it (see logging_config.JsonFormatter), and logs
    one structured line per request with status + latency — this is what
    lets "what happened to request X" be a log-search instead of a
    guess, and is also what /health-check style uptime monitoring and
    APM traces correlate against."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.exception(
            "request failed",
            extra={"method": request.method, "path": request.url.path, "duration_ms": duration_ms},
        )
        raise
    else:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # Baseline hardening headers. CSP is deliberately omitted here — this
    # is an API service (the SPA is a separate static deploy), so a CSP
    # belongs on the frontend's own hosting config, not echoed by the API.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak a stack trace / internal error string to the client — log
    # it server-side (Sentry picks this up too, once SENTRY_DSN is set)
    # and return a generic 500. The request_context middleware's own
    # try/except already logs+re-raises before this handler runs, so this
    # is a deliberately thin final backstop, not a duplicate log site for
    # every field — just the response shape.
    request_id = request_id_var.get()
    content = {"detail": "Internal server error"}
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=500, content=content)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(watchlists.router)
app.include_router(market.router)
app.include_router(prices.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health/ready")
def readiness():
    """Deeper check than /health: confirms the DB is actually reachable,
    for use as a k8s/load-balancer readiness probe (liveness should stay
    on the cheap /health so a slow DB doesn't get the whole pod killed)."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Readiness check: database unreachable")
        db_ok = False

    status_code = 200 if db_ok else 503
    return JSONResponse(status_code=status_code, content={"status": "ok" if db_ok else "degraded", "database": db_ok})
