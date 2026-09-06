from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.models import User, Watchlist, WatchlistItem
from app.schemas import WatchlistCreate, WatchlistOut, ItemCreate, ItemOut, NLAddRequest, NLAddResult
from app.services.nl_intent import resolve_symbols

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=list[WatchlistOut])
def list_watchlists(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Watchlist).filter(Watchlist.user_id == user.id).all()


@router.post("", response_model=WatchlistOut, status_code=201)
def create_watchlist(
    payload: WatchlistCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    wl = Watchlist(user_id=user.id, name=payload.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


def _get_owned_watchlist(watchlist_id: str, db: Session, user: User) -> Watchlist:
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


@router.get("/{watchlist_id}/items", response_model=list[ItemOut])
def list_items(
    watchlist_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    wl = _get_owned_watchlist(watchlist_id, db, user)
    return wl.items


@router.post("/{watchlist_id}/items", response_model=ItemOut, status_code=201)
def add_item(
    watchlist_id: str,
    payload: ItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wl = _get_owned_watchlist(watchlist_id, db, user)
    symbol = payload.symbol.strip().upper()

    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == wl.id, WatchlistItem.symbol == symbol)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Symbol already in this watchlist")

    item = WatchlistItem(watchlist_id=wl.id, symbol=symbol, exchange=payload.exchange)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{watchlist_id}/items/natural-language", response_model=NLAddResult)
def add_items_natural_language(
    watchlist_id: str,
    payload: NLAddRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    e.g. "add the top 3 FMCG large-caps" -> resolves against a fixed,
    curated symbol universe (never an invented ticker — see nl_intent.py)
    and adds whichever of those aren't already on the watchlist.
    """
    wl = _get_owned_watchlist(watchlist_id, db, user)
    symbols, explanation, ai_generated = resolve_symbols(payload.query)

    existing_symbols = {item.symbol for item in wl.items}
    added: list[WatchlistItem] = []
    already_present: list[str] = []

    for symbol in symbols:
        if symbol in existing_symbols:
            already_present.append(symbol)
            continue
        item = WatchlistItem(watchlist_id=wl.id, symbol=symbol, exchange="NSE")
        db.add(item)
        added.append(item)
        existing_symbols.add(symbol)

    db.commit()
    for item in added:
        db.refresh(item)

    return NLAddResult(
        query=payload.query,
        matched_symbols=symbols,
        added=added,
        already_present=already_present,
        ai_generated=ai_generated,
        explanation=explanation,
    )


@router.delete("/{watchlist_id}/items/{symbol}", status_code=204)
def remove_item(
    watchlist_id: str,
    symbol: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wl = _get_owned_watchlist(watchlist_id, db, user)
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == wl.id, WatchlistItem.symbol == symbol.upper())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Symbol not found in this watchlist")
    db.delete(item)
    db.commit()
    return None
