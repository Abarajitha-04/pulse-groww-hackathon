"""
SQLAlchemy models matching the schema in the blueprint (docs/ARCHITECTURE.md, §9).

user_symbol_state is the table that makes "return later and see what changed"
a real, queryable feature rather than a UI trick — every other table is
standard CRUD scaffolding.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Numeric, BigInteger, Integer, UniqueConstraint, Text, JSON,
    Boolean
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

    # Soft-delete flag for account deletion (docs/DECISIONS.md: a hard
    # DELETE would orphan price_snapshots' audit trail and digests other
    # rows may reference; deactivating and scrubbing PII is the safer
    # default, with a real hard-delete job as a documented next step).
    is_active = Column(Boolean, nullable=False, default=True)
    alerts_enabled = Column(Boolean, nullable=False, default=False)

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

    # BigInteger everywhere except SQLite, where autoincrement/rowid-alias
    # behaviour only kicks in for a column declared as exactly INTEGER —
    # a BIGINT primary key silently does NOT get an auto-assigned value on
    # insert, and multi-row inserts in a single flush fail with a NOT
    # NULL constraint error the moment there's more than one row (i.e.
    # the very first time the scheduler polls two or more symbols in one
    # cycle — see docs/DECISIONS.md). `.with_variant` keeps BIGINT's full
    # range in Postgres/production while making SQLite/dev actually work.
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
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

    # Alert de-duplication (see app/services/alert_service.py): records
    # which "baseline" (last_seen_price at alert time) an email has
    # already gone out for, so a still-significant delta doesn't re-alert
    # every poll cycle until the user actually views it (mark_seen resets
    # the baseline) or the price moves meaningfully further.
    last_alerted_price = Column(Numeric, nullable=True)
    last_alerted_at = Column(DateTime(timezone=True), nullable=True)


class Digest(Base):
    """Cache of generated narrative summaries so we don't re-bill the LLM."""
    __tablename__ = "digests"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    watchlist_id = Column(String, ForeignKey("watchlists.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), default=_now)
    content = Column(Text, nullable=False)
    raw_deltas = Column(JSON, nullable=True)


class RefreshToken(Base):
    """Server-side refresh token record — what makes logout and
    revocation actually possible. We store a hash of the token, never
    the token itself, so a leaked database dump doesn't hand over live
    sessions (same principle as password hashing)."""
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(Base):
    """One-time-use password reset token, hashed at rest for the same
    reason as RefreshToken."""
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)


class ChatMessage(Base):
    """Per-user chat history for the watchlist assistant (see
    app/services/chat_service.py). Kept short and prunable — this is
    conversational scaffolding, not a system of record."""
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)
