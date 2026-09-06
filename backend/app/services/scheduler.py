"""
Symbol-centric polling job. Runs once per POLL_INTERVAL_SECONDS, fetches
every DISTINCT symbol across ALL users' watchlists exactly once — this is
the concrete implementation of "the fetch layer is symbol-centric, the
diff layer is user-centric" from the architecture doc.
"""
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import WatchlistItem, PriceSnapshot
from app.services import cache
from app.services.alert_service import check_and_send_alerts
from app.services.price_fetcher import fetch_quote, QuoteFetchError

logger = logging.getLogger("pulse.scheduler")

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def _distinct_symbols(db: Session) -> list[str]:
    rows = db.query(WatchlistItem.symbol).distinct().all()
    return [r[0] for r in rows]


def poll_once() -> None:
    db = SessionLocal()
    try:
        symbols = _distinct_symbols(db)
        for symbol in symbols:
            try:
                quote = fetch_quote(symbol)
            except QuoteFetchError as exc:
                logger.warning("Could not fetch %s this cycle: %s", symbol, exc)
                continue

            cache.set_latest(symbol, quote)
            if _main_loop is not None:
                cache.broadcaster.publish_threadsafe(_main_loop, symbol, quote)

            snapshot = PriceSnapshot(
                symbol=symbol,
                price=quote["price"],
                volume=quote.get("volume"),
                open=quote.get("open"),
                high=quote.get("high"),
                low=quote.get("low"),
                prev_close=quote.get("prev_close"),
                exchange_ts=quote["exchange_ts"],
                ingested_ts=datetime.now(timezone.utc),
                source=quote["source"],
            )
            db.add(snapshot)
        db.commit()
    finally:
        db.close()

    # Runs after prices are committed (it reads the cache diff_engine
    # reads from, which is now current) and in its own try/except so an
    # email-sending problem can never take down the price poll itself.
    try:
        check_and_send_alerts()
    except Exception:
        logger.exception("check_and_send_alerts failed this cycle")


scheduler = BackgroundScheduler()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.add_job(
            poll_once,
            "interval",
            seconds=settings.POLL_INTERVAL_SECONDS,
            id="poll_prices",
            next_run_time=datetime.now(timezone.utc),  # fetch immediately on startup
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
