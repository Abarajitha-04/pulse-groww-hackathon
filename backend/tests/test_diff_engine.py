from datetime import datetime, timezone

from app.models.models import PriceSnapshot, UserSymbolState
from app.services import cache, diff_engine


def _seed_history(db, symbol: str, prices: list[float]):
    now = datetime.now(timezone.utc)
    for i, p in enumerate(prices):
        db.add(
            PriceSnapshot(
                symbol=symbol,
                price=p,
                volume=1000 + i,
                exchange_ts=now,
                source="test",
            )
        )
    db.commit()


def test_no_live_data_returns_safe_default(db_session):
    result = diff_engine.compute_delta_for_symbol(db_session, "user-1", "GHOST.NS")
    assert result["significant"] is False
    assert result["current_price"] is None
    assert "No live data" in result["reason"]


def test_first_view_is_flagged_significant(db_session):
    cache.set_latest("RELIANCE.NS", {
        "price": 2500.0, "volume": 100000, "exchange_ts": datetime.now(timezone.utc), "source": "test",
    })
    result = diff_engine.compute_delta_for_symbol(db_session, "user-1", "RELIANCE.NS")
    assert result["significant"] is True
    assert result["last_seen_price"] is None


def test_mark_seen_then_no_change_is_not_significant(db_session):
    cache.set_latest("TCS.NS", {
        "price": 3500.0, "volume": 50000, "exchange_ts": datetime.now(timezone.utc), "source": "test",
    })
    diff_engine.mark_seen(db_session, "user-1", "TCS.NS")

    result = diff_engine.compute_delta_for_symbol(db_session, "user-1", "TCS.NS")
    assert result["significant"] is False
    assert result["last_seen_price"] == 3500.0


def test_watermark_is_per_user_not_global(db_session):
    """Two different users watching the same symbol must get independent
    deltas — this is the concrete test of the 'shared fetch, per-user diff'
    architecture claim."""
    cache.set_latest("INFY.NS", {
        "price": 1500.0, "volume": 20000, "exchange_ts": datetime.now(timezone.utc), "source": "test",
    })
    diff_engine.mark_seen(db_session, "user-A", "INFY.NS")

    # Price moves after user-A has already seen it.
    cache.set_latest("INFY.NS", {
        "price": 1560.0, "volume": 20000, "exchange_ts": datetime.now(timezone.utc), "source": "test",
    })

    result_a = diff_engine.compute_delta_for_symbol(db_session, "user-A", "INFY.NS")
    result_b = diff_engine.compute_delta_for_symbol(db_session, "user-B", "INFY.NS")

    assert result_a["last_seen_price"] == 1500.0
    assert result_b["last_seen_price"] is None  # user-B never marked it seen
    assert result_b["significant"] is True  # first view for user-B


def test_stale_data_suppresses_significance_even_if_move_is_real(db_session, monkeypatch):
    from datetime import timedelta

    old_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    cache.set_latest("WIPRO.NS", {
        "price": 400.0, "volume": 5000, "exchange_ts": old_ts, "source": "test",
    })
    diff_engine.mark_seen(db_session, "user-1", "WIPRO.NS")
    cache.set_latest("WIPRO.NS", {
        "price": 440.0, "volume": 5000, "exchange_ts": old_ts, "source": "test",
    })

    monkeypatch.setattr(diff_engine, "is_market_open_now", lambda now=None: True)

    result = diff_engine.compute_delta_for_symbol(db_session, "user-1", "WIPRO.NS")
    assert result["stale"] is True
    assert result["significant"] is False, "a stale quote must never be presented as a confirmed signal"
    assert "STALE" in result["reason"]
