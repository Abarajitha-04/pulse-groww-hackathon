"""
Provider registry. `get_provider()` returns a singleton instance chosen by
settings.MARKET_DATA_PROVIDER — this is the one place that decision gets
made; nothing else in the app imports a concrete provider class directly.
"""
from app.core.config import settings
from app.services.market_data.base import MarketDataProvider, QuoteFetchError  # noqa: F401 — re-exported

_provider: MarketDataProvider | None = None


def get_provider() -> MarketDataProvider:
    global _provider
    if _provider is None:
        if settings.MARKET_DATA_PROVIDER == "groww":
            from app.services.market_data.groww_provider import GrowwProvider

            _provider = GrowwProvider()
        else:
            from app.services.market_data.auto_provider import AutoProvider

            _provider = AutoProvider()
    return _provider


def reset_provider_for_tests() -> None:
    global _provider
    _provider = None
