"""
Significant-move email alerts.

Runs once per poll cycle (see scheduler.py), after prices are ingested —
it deliberately reuses diff_engine.compute_delta_for_symbol rather than
its own significance logic, so "what counts as significant" has exactly
one definition in the codebase, whether it's shown in the UI or emailed.

De-duplication: a delta stays "significant" across many poll cycles until
the user actually looks at it (mark_seen resets their watermark), so
without guarding against that this would email the same move every
POLL_INTERVAL_SECONDS. UserSymbolState.last_alerted_price records the
baseline (last_seen_price) an alert already went out for; we only alert
again once that baseline changes — either because the user viewed it
(mark_seen) or the price has moved by another full significance step
since the alert (re-checked against the live significance evaluation,
not a fixed re-alert timer). Known, documented limitation: this means a
single continuous move only ever emails once until viewed — an
intermediate step model with time-decay is a reasonable v2, not needed
to be correct for v1.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.models import User, Watchlist, WatchlistItem, UserSymbolState
from app.services import diff_engine
from app.services.notification_service import send_significant_move_alert

logger = logging.getLogger("pulse.alerts")


def _distinct_alertable_items(db: Session) -> list[tuple[User, str]]:
    """(user, symbol) pairs for every user who has alerts turned on,
    across all of their watchlists — deduplicated so a symbol on two of
    one user's watchlists doesn't alert twice."""
    rows = (
        db.query(User, WatchlistItem.symbol)
        .join(Watchlist, Watchlist.user_id == User.id)
        .join(WatchlistItem, WatchlistItem.watchlist_id == Watchlist.id)
        .filter(User.alerts_enabled.is_(True), User.is_active.is_(True))
        .distinct()
        .all()
    )
    return [(user, symbol) for user, symbol in rows]


def check_and_send_alerts(db: Session | None = None) -> None:
    """Accepts an optional session (tests pass the isolated per-test
    session so assertions see the same data this function wrote;
    scheduler.py calls it with no argument, so it opens and closes its
    own — the normal pattern for a background-job entry point)."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        for user, symbol in _distinct_alertable_items(db):
            delta = diff_engine.compute_delta_for_symbol(db, user.id, symbol)
            if not delta["significant"]:
                continue

            state = (
                db.query(UserSymbolState)
                .filter(UserSymbolState.user_id == user.id, UserSymbolState.symbol == symbol)
                .first()
            )
            # A user's very first view of a symbol has no last_seen_price
            # (baseline is None) and is always flagged significant — using
            # -1 as an explicit "no baseline yet" sentinel (a real price
            # is never <= 0) lets that case be de-duplicated the same way
            # as every other baseline, instead of comparing None == None
            # against a column that was never actually written to (the
            # bug this comment is here to stop someone reintroducing:
            # `baseline is not None` in this check silently disabled
            # dedup entirely for first-view alerts, verified interactively
            # before this fix).
            baseline = delta["last_seen_price"]
            baseline_key = float(baseline) if baseline is not None else -1.0
            already_alerted_for_this_baseline = (
                state is not None
                and state.last_alerted_price is not None
                and float(state.last_alerted_price) == baseline_key
            )
            if already_alerted_for_this_baseline:
                continue

            summary = (
                f"{symbol} moved {delta['price_change_pct'] * 100:+.2f}% "
                f"(now {delta['current_price']}). {delta['reason']}"
                if delta["price_change_pct"] is not None
                else f"{symbol}: {delta['reason']}"
            )
            try:
                send_significant_move_alert(user.email, symbol, summary)
            except Exception:
                # A notification failure must never break ingestion for
                # everyone else in the loop.
                logger.exception("Failed to send alert to %s for %s", user.email, symbol)
                continue

            if state is None:
                state = UserSymbolState(user_id=user.id, symbol=symbol)
                db.add(state)
            state.last_alerted_price = baseline_key
            state.last_alerted_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        if owns_session:
            db.close()
