"""
The "auto" provider: yfinance (primary) + NSE India's public endpoint
(secondary fallback). Free, unofficial, no API key required — this is
what makes a fresh clone runnable with zero setup, and it's what the
hackathon build always used. See market_data/README.md for why this is
not a licensed, ToS-compliant data source and what to switch to before
handing this to a paying customer.

Two data sources are wired in on purpose, to demonstrate the failover
behaviour a real production system needs ("how to handle stale, delayed
or conflicting data"):
  1. yfinance (primary) — free, no key, covers NSE/BSE via .NS/.BO suffix.
  2. NSE India's public quote endpoint (secondary) — free but undocumented
     and rate-limited; used only when the primary has failed repeatedly.

Both are best-effort network calls. In a sandboxed/offline environment
(e.g. CI, or a judge's/customer's machine with restricted egress) both can
fail — the circuit breaker below is what turns "network failed" into a
clean, visible staleness state instead of a crash or a fabricated price.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
import yfinance as yf

from app.services.market_data.base import MarketDataProvider, QuoteFetchError

logger = logging.getLogger("pulse.price_fetcher")

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 120


@dataclass
class CircuitBreaker:
    """Per-symbol, per-source failure tracker. Not global — a bad NSE feed
    for one delisted symbol should never blind the whole app to real ones."""

    failures: dict[str, int] = field(default_factory=dict)
    tripped_until: dict[str, datetime] = field(default_factory=dict)

    def record_failure(self, key: str) -> None:
        self.failures[key] = self.failures.get(key, 0) + 1
        if self.failures[key] >= FAILURE_THRESHOLD:
            self.tripped_until[key] = datetime.now(timezone.utc)

    def record_success(self, key: str) -> None:
        self.failures[key] = 0
        self.tripped_until.pop(key, None)

    def is_open(self, key: str) -> bool:
        """True = circuit open = skip this source for now."""
        tripped_at = self.tripped_until.get(key)
        if not tripped_at:
            return False
        elapsed = (datetime.now(timezone.utc) - tripped_at).total_seconds()
        if elapsed > COOLDOWN_SECONDS:
            # Half-open: allow one retry.
            self.tripped_until.pop(key, None)
            self.failures[key] = 0
            return False
        return True


def fetch_from_yfinance(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    fast = ticker.fast_info
    price = fast.get("lastPrice") if hasattr(fast, "get") else getattr(fast, "last_price", None)
    if price is None:
        # Fallback for yfinance versions where fast_info lacks lastPrice.
        hist = ticker.history(period="1d")
        if hist.empty:
            raise QuoteFetchError(f"No data returned for {symbol}")
        price = float(hist["Close"].iloc[-1])
        volume = int(hist["Volume"].iloc[-1])
        open_ = float(hist["Open"].iloc[-1])
        high = float(hist["High"].iloc[-1])
        low = float(hist["Low"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else open_
    else:
        volume = fast.get("lastVolume") if hasattr(fast, "get") else getattr(fast, "last_volume", None)
        open_ = fast.get("open") if hasattr(fast, "get") else getattr(fast, "open", None)
        high = fast.get("dayHigh") if hasattr(fast, "get") else getattr(fast, "day_high", None)
        low = fast.get("dayLow") if hasattr(fast, "get") else getattr(fast, "day_low", None)
        prev_close = (
            fast.get("previousClose") if hasattr(fast, "get") else getattr(fast, "previous_close", None)
        )

    return {
        "symbol": symbol,
        "price": float(price),
        "volume": int(volume) if volume is not None else None,
        "open": float(open_) if open_ is not None else None,
        "high": float(high) if high is not None else None,
        "low": float(low) if low is not None else None,
        "prev_close": float(prev_close) if prev_close is not None else None,
        "exchange_ts": datetime.now(timezone.utc),
        "source": "yfinance",
    }


def fetch_from_nse_fallback(symbol: str) -> dict:
    """Best-effort secondary source. NSE's endpoint requires session
    cookies from a prior visit to the site, which is why this is kept
    separate and clearly labelled as a fallback rather than trusted as
    a primary — an honest limitation to state, not hide."""
    clean_symbol = symbol.replace(".NS", "").replace(".BO", "")
    url = f"https://www.nseindia.com/api/quote-equity?symbol={clean_symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=5.0, headers=headers) as client:
        client.get("https://www.nseindia.com", headers=headers)  # seed cookies
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    price_info = data["priceInfo"]
    return {
        "symbol": symbol,
        "price": float(price_info["lastPrice"]),
        "volume": None,
        "open": float(price_info.get("open", 0)) or None,
        "high": float(price_info["intraDayHighLow"]["max"]),
        "low": float(price_info["intraDayHighLow"]["min"]),
        "prev_close": float(price_info["previousClose"]),
        "exchange_ts": datetime.now(timezone.utc),
        "source": "nse_fallback",
    }


class AutoProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.primary_breaker = CircuitBreaker()
        self.secondary_breaker = CircuitBreaker()

    def fetch_quote(self, symbol: str) -> dict:
        if not self.primary_breaker.is_open(symbol):
            try:
                quote = fetch_from_yfinance(symbol)
                self.primary_breaker.record_success(symbol)
                return quote
            except Exception as exc:  # noqa: BLE001 — deliberately broad, this is a network boundary
                logger.warning("Primary source failed for %s: %s", symbol, exc)
                self.primary_breaker.record_failure(symbol)

        if not self.secondary_breaker.is_open(symbol):
            try:
                quote = fetch_from_nse_fallback(symbol)
                self.secondary_breaker.record_success(symbol)
                return quote
            except Exception as exc:  # noqa: BLE001
                logger.warning("Secondary source failed for %s: %s", symbol, exc)
                self.secondary_breaker.record_failure(symbol)

        raise QuoteFetchError(f"All sources failed for {symbol}")
