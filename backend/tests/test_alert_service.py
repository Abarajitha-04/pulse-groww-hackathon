"""
Covers two things found and fixed together during production hardening:

1. PriceSnapshot.id was a plain BigInteger primary key, which SQLite only
   auto-assigns for a column declared as exactly INTEGER (see
   app/models/models.py and docs/DECISIONS.md) — inserting more than one
   row in a single flush crashed with a NOT NULL constraint error. This
   would have hit the scheduler's very first poll cycle with 2+ symbols.
2. alert_service's de-duplication used `baseline is not None` as a guard,
   which meant a first-view alert (baseline=None) could never be marked
   "already alerted" and would re-fire every poll cycle.

Both are regression tests, not just feature tests — each asserts the
specific failure mode that was actually observed, not just the happy path.
"""
from datetime import datetime, timedelta, timezone

from app.models.models import PriceSnapshot, User, UserSymbolState, Watchlist, WatchlistItem
from app.core.security import hash_password
from app.services import alert_service, cache, diff_engine


def _make_user_with_symbol(db, symbol: str, alerts_enabled: bool = True) -> User:
    user = User(email=f"{symbol.lower()}@example.com", password_hash=hash_password("x"), alerts_enabled=alerts_enabled)
    db.add(user)
    db.commit()
    db.refresh(user)
    wl = Watchlist(user_id=user.id, name="WL")
    db.add(wl)
    db.commit()
    db.refresh(wl)
    db.add(WatchlistItem(watchlist_id=wl.id, symbol=symbol))
    db.commit()
    return user


def test_multi_row_price_snapshot_insert_does_not_crash_on_sqlite(db_session):
    """Regression test for the BigInteger-on-SQLite autoincrement bug:
    committing several PriceSnapshot rows in one flush (exactly what
    scheduler.poll_once does for N watched symbols) must not raise."""
    now = datetime.now(timezone.utc)
    for i in range(10):
        db_session.add(PriceSnapshot(symbol=f"SYM{i}.NS", price=100 + i, exchange_ts=now, source="test"))
    db_session.commit()  # would raise IntegrityError before the fix

    assert db_session.query(PriceSnapshot).count() == 10


def test_first_view_alert_is_not_resent_every_cycle(db_session):
    """Regression test for the None-baseline dedup bug: a first-time
    significant view (last_seen_price is None) must only alert once,
    not on every subsequent check_and_send_alerts() call."""
    user = _make_user_with_symbol(db_session, "FIRSTVIEW.NS")
    now = datetime.now(timezone.utc)
    for i in range(20):
        db_session.add(
            PriceSnapshot(
                symbol="FIRSTVIEW.NS", price=100 + (i % 2) * 0.05,
                exchange_ts=now - timedelta(minutes=20 - i), source="test",
            )
        )
    db_session.commit()
    cache.set_latest("FIRSTVIEW.NS", {
        "symbol": "FIRSTVIEW.NS", "price": 115.0, "volume": 1000,
        "exchange_ts": now, "source": "test",
    })

    sent = []
    import app.services.alert_service as mod
    mod.send_significant_move_alert = lambda *a, **k: sent.append(a)

    alert_service.check_and_send_alerts(db_session)
    alert_service.check_and_send_alerts(db_session)
    alert_service.check_and_send_alerts(db_session)

    assert len(sent) == 1, "a first-view significant delta must alert exactly once until viewed or it moves further"


def test_alert_fires_again_after_view_and_a_new_significant_move(db_session):
    """After the user views the symbol (mark_seen resets the watermark)
    and price moves significantly again, a new alert must go out — dedup
    should key off the baseline, not become a permanent one-time-ever
    suppression."""
    user = _make_user_with_symbol(db_session, "RENEW.NS")
    now = datetime.now(timezone.utc)
    for i in range(20):
        db_session.add(
            PriceSnapshot(
                symbol="RENEW.NS", price=100 + (i % 2) * 0.05,
                exchange_ts=now - timedelta(minutes=20 - i), source="test",
            )
        )
    db_session.commit()
    cache.set_latest("RENEW.NS", {
        "symbol": "RENEW.NS", "price": 115.0, "volume": 1000, "exchange_ts": now, "source": "test",
    })

    sent = []
    import app.services.alert_service as mod
    mod.send_significant_move_alert = lambda *a, **k: sent.append(a)

    alert_service.check_and_send_alerts(db_session)
    assert len(sent) == 1

    diff_engine.mark_seen(db_session, user.id, "RENEW.NS")
    alert_service.check_and_send_alerts(db_session)
    assert len(sent) == 1, "no new move since the view — must not alert again"

    cache.set_latest("RENEW.NS", {
        "symbol": "RENEW.NS", "price": 130.0, "volume": 1000, "exchange_ts": now, "source": "test",
    })
    alert_service.check_and_send_alerts(db_session)
    assert len(sent) == 2, "a genuinely new significant move after the view must alert again"


def test_alerts_disabled_user_is_never_contacted(db_session):
    _make_user_with_symbol(db_session, "QUIET.NS", alerts_enabled=False)
    now = datetime.now(timezone.utc)
    cache.set_latest("QUIET.NS", {
        "symbol": "QUIET.NS", "price": 500.0, "volume": 100, "exchange_ts": now, "source": "test",
    })

    sent = []
    import app.services.alert_service as mod
    mod.send_significant_move_alert = lambda *a, **k: sent.append(a)

    alert_service.check_and_send_alerts(db_session)
    assert sent == []
