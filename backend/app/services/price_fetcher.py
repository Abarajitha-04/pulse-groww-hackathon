"""
Backward-compatible entry point: `from app.services.price_fetcher import
fetch_quote, QuoteFetchError` is what scheduler.py (and anything else
written before the provider abstraction landed) expects. The actual
provider selection and implementations live in app/services/market_data/
— see that package's README for the "auto" vs "groww" trade-off.
"""
from app.services.market_data import get_provider
from app.services.market_data.base import QuoteFetchError  # noqa: F401 — re-exported for existing callers


def fetch_quote(symbol: str) -> dict:
    return get_provider().fetch_quote(symbol)
