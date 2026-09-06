"""
Per-user diff engine.

This is deliberately the cheapest part of the system computationally
(it never calls an external API) and the most important part
product-wise: it answers "what changed since I last looked," which is
the entire premise of the brief.

It reads:
  - the shared latest quote from the cache (one fetch, shared by everyone)
  - this user's watermark (UserSymbolState) — last price/volume THEY saw
  - a short history of past snapshots for this symbol, to estimate volatility

...and produces a structured, explainable delta. No LLM involved here —
the digest generator downstream only narrates these already-correct
numbers, so the AI layer can never invent a figure.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import PriceSnapshot, UserSymbolState
from app.services import cache
from app.services.significance import evaluate_significance, evaluate_volume_change


def is_market_open_now(now: datetime | None = None) -> bool:
    """NSE trading hours: 9:15–15:30 IST, Mon–Fri. Kept simple on purpose —
    no holiday calendar for a 72-hour build; the honest gap is noted in
    docs/DECISIONS.md and does not affect correctness of the delta math,
    only the 'stale' label's phrasing."""
    now = now or datetime.now(timezone.utc)
    ist = now.astimezone(timezone.utc)
    ist_minutes = (ist.hour * 60 + ist.minute + 330) % 1440  # +5:30 in minutes
    weekday = ist.weekday()  # Monday = 0
    if weekday >= 5:
        return False
    return 9 * 60 + 15 <= ist_minutes <= 15 * 60 + 30


def get_recent_closes(db: Session, symbol: str, limit: int = 30) -> list[float]:
    rows = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.symbol == symbol)
        .order_by(PriceSnapshot.exchange_ts.desc())
        .limit(limit)
        .all()
    )
    prices = [float(r.price) for r in reversed(rows)]
    return prices


def compute_delta_for_symbol(db: Session, user_id: str, symbol: str) -> dict:
    latest = cache.get_latest(symbol)

    if latest is None:
        return {
            "symbol": symbol,
            "significant": False,
            "price_change_pct": None,
            "price_z_score": None,
            "volume_change_pct": None,
            "current_price": None,
            "last_seen_price": None,
            "last_viewed_at": None,
            "reason": "No live data available yet for this symbol",
        }

    seconds_since_update = (datetime.now(timezone.utc) - latest["exchange_ts"]).total_seconds()
    stale = seconds_since_update > settings.STALENESS_SECONDS and is_market_open_now()

    state = (
        db.query(UserSymbolState)
        .filter(UserSymbolState.user_id == user_id, UserSymbolState.symbol == symbol)
        .first()
    )
    last_seen_price = float(state.last_seen_price) if state and state.last_seen_price is not None else None
    last_seen_volume = int(state.last_seen_volume) if state and state.last_seen_volume is not None else None
    last_viewed_at = state.last_viewed_at if state else None

    history = get_recent_closes(db, symbol, limit=30)
    sig = evaluate_significance(
        historical_prices=history,
        current_price=latest["price"],
        last_seen_price=last_seen_price,
        z_threshold=settings.SIGNIFICANCE_Z_THRESHOLD,
        min_history_points=settings.MIN_HISTORY_POINTS,
    )
    vol_change = evaluate_volume_change(latest.get("volume"), last_seen_volume)

    price_change_pct = None
    if last_seen_price:
        price_change_pct = (latest["price"] - last_seen_price) / last_seen_price

    reason = sig.reason
    if stale:
        reason = f"[STALE DATA — last update {int(seconds_since_update)}s ago] {reason}"

    return {
        "symbol": symbol,
        "significant": sig.is_significant and not stale,
        "price_change_pct": round(price_change_pct, 5) if price_change_pct is not None else None,
        "price_z_score": sig.z_score,
        "volume_change_pct": round(vol_change, 5) if vol_change is not None else None,
        "current_price": latest["price"],
        "last_seen_price": last_seen_price,
        "last_viewed_at": last_viewed_at,
        "reason": reason,
        "stale": stale,
        "source": latest.get("source"),
    }


def mark_seen(db: Session, user_id: str, symbol: str) -> None:
    """Explicit endpoint-driven watermark update (see API §10 rationale):
    the frontend calls this only after the user has actually seen the
    delta, not on every page load, so we don't erase the signal before
    it's read."""
    latest = cache.get_latest(symbol)
    if latest is None:
        return

    state = (
        db.query(UserSymbolState)
        .filter(UserSymbolState.user_id == user_id, UserSymbolState.symbol == symbol)
        .first()
    )
    if state is None:
        state = UserSymbolState(user_id=user_id, symbol=symbol)
        db.add(state)

    state.last_viewed_at = datetime.now(timezone.utc)
    state.last_seen_price = latest["price"]
    state.last_seen_volume = latest.get("volume")
    db.commit()
