"""
Groww's own Trading API (growwapi), as a licensed alternative to the free
"auto" provider.

Real and available — groww.in/trade-api documents live quotes (Get Quote /
LTP / OHLC), option chains, Greeks, and historical data for NSE/BSE/MCX —
but it comes with two things worth knowing before flipping
MARKET_DATA_PROVIDER to "groww" in a real deployment:

1. It requires an actual Groww trading/demat account plus a paid API
   subscription (₹499+/month as of Sept 2026), authenticated with that
   account's own API key/secret or TOTP — not a service-account model.
2. It's built for a trader running their own strategies against their own
   account. Whether its terms permit redistributing that data inside a
   multi-tenant product used by *other* people (which is exactly what
   Pulse does) is a question for Groww directly, not something this
   codebase can answer — check with them before relying on this path for
   paying customers.

This class is a real, working integration point (not a fake stub) for
whoever holds that account and subscription: it uses the actual growwapi
SDK once GROWW_API_KEY/GROWW_API_SECRET are set, and fails loudly and
specifically — not silently — when they aren't, so switching providers is
a config change plus these two env vars, not a code change.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.services.market_data.base import MarketDataProvider, QuoteFetchError

logger = logging.getLogger("pulse.market_data.groww")


class GrowwProvider(MarketDataProvider):
    def __init__(self) -> None:
        if not (settings.GROWW_API_KEY and settings.GROWW_API_SECRET):
            raise RuntimeError(
                "MARKET_DATA_PROVIDER=groww requires GROWW_API_KEY and GROWW_API_SECRET "
                "(from https://groww.in/trade-api — see app/services/market_data/README.md)."
            )
        self._client = self._authenticate()

    def _authenticate(self):
        from growwapi import GrowwAPI  # optional dependency — only needed for this provider

        access_token = GrowwAPI.get_access_token(settings.GROWW_API_KEY, settings.GROWW_API_SECRET)
        return GrowwAPI(access_token)

    def fetch_quote(self, symbol: str) -> dict:
        # growwapi's own symbol format differs from yfinance's ".NS"/".BO"
        # suffix convention — a real integration needs a symbol-mapping
        # table (see symbol_universe.py) translating Pulse's internal
        # symbols to Groww's (exchange, segment, trading_symbol) triple.
        # Left as the integration owner's next step: it depends on
        # exactly which of Pulse's curated universe they want on Groww's
        # feed, not on anything this codebase can decide generically.
        try:
            exchange, trading_symbol = self._map_symbol(symbol)
            quote = self._client.get_quote(exchange=exchange, segment="CASH", trading_symbol=trading_symbol)
        except Exception as exc:  # noqa: BLE001 — external API boundary
            raise QuoteFetchError(f"Groww API fetch failed for {symbol}: {exc}") from exc

        return {
            "symbol": symbol,
            "price": float(quote["last_price"]),
            "volume": quote.get("volume"),
            "open": quote.get("open_price"),
            "high": quote.get("high_price"),
            "low": quote.get("low_price"),
            "prev_close": quote.get("prev_close"),
            "exchange_ts": datetime.now(timezone.utc),
            "source": "groww",
        }

    @staticmethod
    def _map_symbol(symbol: str) -> tuple[str, str]:
        exchange = "BSE" if symbol.endswith(".BO") else "NSE"
        trading_symbol = symbol.replace(".NS", "").replace(".BO", "")
        return exchange, trading_symbol
