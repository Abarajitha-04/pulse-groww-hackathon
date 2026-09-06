"""
The provider interface every market-data source implements.

Kept deliberately tiny — one method, one exception type — because the
only thing the rest of the app (scheduler.py, and everything downstream
of the cache) needs from a provider is "give me one honest quote for this
symbol, or tell me you couldn't." Significance, diffing, alerts, and the
cache are all provider-agnostic; they only ever see the dict shape below.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class QuoteFetchError(Exception):
    """Raised when a provider cannot produce a quote for a symbol this
    cycle. Callers (scheduler.py) treat this as "skip this symbol until
    the next poll," never as a reason to fabricate a price."""


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_quote(self, symbol: str) -> dict:
        """Returns a dict with exactly this shape:
            {
                "symbol": str, "price": float, "volume": int | None,
                "open": float | None, "high": float | None, "low": float | None,
                "prev_close": float | None,
                "exchange_ts": datetime (tz-aware, UTC),
                "source": str,  # short label — shown to users as data provenance
            }
        Raises QuoteFetchError if no quote could be obtained.
        """
        raise NotImplementedError
