import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, watchlists, market
from app.core.config import settings
from app.db.session import Base, engine
from app.services.scheduler import start_scheduler, set_main_loop
from app.ws import prices

logging.basicConfig(level=logging.INFO)

# Deliberate simplicity: Base.metadata.create_all() instead of Alembic
# migrations. For a 72-hour solo build with one, append-mostly schema,
# a migration framework is complexity with no payoff yet — see
# docs/DECISIONS.md. Swapping to Alembic later is a mechanical step.
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(watchlists.router)
app.include_router(market.router)
app.include_router(prices.router)


@app.on_event("startup")
def on_startup():
    set_main_loop(asyncio.get_event_loop())
    start_scheduler()


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
