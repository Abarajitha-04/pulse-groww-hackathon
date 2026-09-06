"""Pydantic request/response models — kept in one file deliberately (small
surface area, easier to scan than a package of one-liners)."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WatchlistCreate(BaseModel):
    name: str = "My Watchlist"


class WatchlistOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class ItemCreate(BaseModel):
    symbol: str
    exchange: str = "NSE"


class ItemOut(BaseModel):
    id: str
    symbol: str
    exchange: str
    added_at: datetime

    class Config:
        from_attributes = True


class QuoteOut(BaseModel):
    symbol: str
    price: float
    volume: int | None
    open: float | None
    high: float | None
    low: float | None
    prev_close: float | None
    exchange_ts: datetime
    source: str
    stale: bool
    seconds_since_update: float


class DeltaOut(BaseModel):
    symbol: str
    significant: bool
    price_change_pct: float | None
    price_z_score: float | None
    volume_change_pct: float | None
    current_price: float | None
    last_seen_price: float | None
    last_viewed_at: datetime | None
    reason: str


class HistoryPoint(BaseModel):
    price: float
    exchange_ts: datetime


class HistoryOut(BaseModel):
    symbol: str
    points: list[HistoryPoint]


class NLAddRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)


class NLAddResult(BaseModel):
    query: str
    matched_symbols: list[str]
    added: list[ItemOut]
    already_present: list[str]
    ai_generated: bool
    explanation: str


class DigestOut(BaseModel):
    watchlist_id: str
    generated_at: datetime
    content: str
    deltas: list[DeltaOut]
    ai_generated: bool
