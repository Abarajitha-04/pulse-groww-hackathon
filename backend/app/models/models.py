"""
SQLAlchemy models matching the schema in the blueprint (docs/ARCHITECTURE.md, §9).

user_symbol_state is the table that makes "return later and see what changed"
a real, queryable feature rather than a UI trick — every other table is
standard CRUD scaffolding.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Numeric, BigInteger, UniqueConstraint, Text, JSON
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    watchlists = relationship("Watchlist", back_populates="owner", cascade="all, delete-orphan")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False, default="My Watchlist")
    created_at = Column(DateTime(timezone=True), default=_now)

    owner = relationship("User", back_populates="watchlists")
    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),)

    id = Column(String, primary_key=True, default=_uuid)
    watchlist_id = Column(String, ForeignKey("watchlists.id"), nullable=False)
    symbol = Column(String, nullable=False)          # e.g. "RELIANCE.NS"
    exchange = Column(String, nullable=False, default="NSE")
    added_at = Column(DateTime(timezone=True), default=_now)

    watchlist = relationship("Watchlist", back_populates="items")


class PriceSnapshot(Base):
    """Append-only. The single source of truth the diff engine reads from."""
    __tablename__ = "price_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    price = Column(Numeric, nullable=False)
    volume = Column(BigInteger, nullable=True)
    open = Column(Numeric, nullable=True)
    high = Column(Numeric, nullable=True)
    low = Column(Numeric, nullable=True)
    prev_close = Column(Numeric, nullable=True)
    exchange_ts = Column(DateTime(timezone=True), nullable=False)
    ingested_ts = Column(DateTime(timezone=True), default=_now)
    source = Column(String, nullable=False, default="yfinance")


class UserSymbolState(Base):
    """The 'last seen' watermark per user per symbol — the core of the product."""
    __tablename__ = "user_symbol_state"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    symbol = Column(String, primary_key=True)
    last_viewed_at = Column(DateTime(timezone=True), default=_now)
    last_seen_price = Column(Numeric, nullable=True)
    last_seen_volume = Column(BigInteger, nullable=True)


class Digest(Base):
    """Cache of generated narrative summaries so we don't re-bill the LLM."""
    __tablename__ = "digests"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    watchlist_id = Column(String, ForeignKey("watchlists.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), default=_now)
    content = Column(Text, nullable=False)
    raw_deltas = Column(JSON, nullable=True)
