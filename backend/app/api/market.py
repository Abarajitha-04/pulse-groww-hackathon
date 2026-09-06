from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.models import User, Watchlist, Digest, PriceSnapshot
from app.schemas import QuoteOut, DeltaOut, DigestOut, HistoryOut, HistoryPoint
from app.services import cache, diff_engine, digest_generator

router = APIRouter(tags=["market"])


@router.get("/market/quote/{symbol}", response_model=QuoteOut)
def get_quote(symbol: str, _: User = Depends(get_current_user)):
    symbol = symbol.upper()
    latest = cache.get_latest(symbol)
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail="No data yet for this symbol — it may not be on any watchlist, "
            "or the next poll cycle hasn't run.",
        )
    seconds_since = (datetime.now(timezone.utc) - latest["exchange_ts"]).total_seconds()
    return QuoteOut(
        symbol=symbol,
        price=latest["price"],
        volume=latest.get("volume"),
        open=latest.get("open"),
        high=latest.get("high"),
        low=latest.get("low"),
        prev_close=latest.get("prev_close"),
        exchange_ts=latest["exchange_ts"],
        source=latest["source"],
        stale=seconds_since > settings.STALENESS_SECONDS,
        seconds_since_update=round(seconds_since, 1),
    )


@router.get("/market/history/{symbol}", response_model=HistoryOut)
def get_history(symbol: str, limit: int = 30, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Recent closes for a sparkline — deliberately just the append-only
    snapshot table, no separate time-series store. Good enough for a
    30-60 point sparkline; a real OHLC chart would want a dedicated
    candles table, which is out of scope for the 72-hour build."""
    symbol = symbol.upper()
    limit = max(2, min(limit, 200))
    rows = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.symbol == symbol)
        .order_by(PriceSnapshot.exchange_ts.desc())
        .limit(limit)
        .all()
    )
    points = [HistoryPoint(price=float(r.price), exchange_ts=r.exchange_ts) for r in reversed(rows)]
    return HistoryOut(symbol=symbol, points=points)


def _get_owned_watchlist(watchlist_id: str, db: Session, user: User) -> Watchlist:
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


@router.get("/watchlists/{watchlist_id}/changes", response_model=list[DeltaOut])
def get_changes(
    watchlist_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    wl = _get_owned_watchlist(watchlist_id, db, user)
    deltas = [diff_engine.compute_delta_for_symbol(db, user.id, item.symbol) for item in wl.items]
    return deltas


@router.post("/watchlists/{watchlist_id}/mark-seen", status_code=204)
def mark_seen(
    watchlist_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    wl = _get_owned_watchlist(watchlist_id, db, user)
    for item in wl.items:
        diff_engine.mark_seen(db, user.id, item.symbol)
    return None


@router.get("/watchlists/{watchlist_id}/digest", response_model=DigestOut)
def get_digest(
    watchlist_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    wl = _get_owned_watchlist(watchlist_id, db, user)
    deltas = [diff_engine.compute_delta_for_symbol(db, user.id, item.symbol) for item in wl.items]

    text, ai_generated = digest_generator.generate_digest(deltas)

    record = Digest(
        user_id=user.id,
        watchlist_id=wl.id,
        content=text,
        raw_deltas=[{**d, "last_viewed_at": str(d["last_viewed_at"])} for d in deltas],
    )
    db.add(record)
    db.commit()

    return DigestOut(
        watchlist_id=wl.id,
        generated_at=record.generated_at,
        content=text,
        deltas=deltas,
        ai_generated=ai_generated,
    )
