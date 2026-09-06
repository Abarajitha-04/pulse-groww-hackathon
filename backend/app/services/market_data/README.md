# Market data providers

Pulse's price ingestion goes through a small provider interface
(`base.py: MarketDataProvider`) so the rest of the app — the diff engine,
significance model, alerts, cache, everything — never knows or cares
which upstream feed a quote came from. Pick a provider with
`MARKET_DATA_PROVIDER` in `.env`.

## `auto` (default)

yfinance (primary) + NSE India's public quote endpoint (fallback), with
per-symbol circuit breakers so a failing source degrades gracefully
instead of taking down the whole poll cycle. Free, no account or API key
needed — this is what makes `git clone && run` work with zero setup, and
it's what the original hackathon build used throughout.

**Not suitable for a paying customer's production deployment as-is**:
neither yfinance nor NSE's undocumented endpoint comes with an SLA, a
commercial-use license, or a support contract. Treat it as a dev/demo
default, not a vendor relationship.

## `groww`

Groww's own [Trading API](https://groww.in/trade-api) — a real, licensed
option, not a placeholder. It offers live quotes (Get Quote / LTP / OHLC),
option chains, Greeks, and historical data for NSE/BSE/MCX via the
`growwapi` Python SDK (`pip install growwapi`).

To use it:

1. Get a Groww trading/demat account and an active API subscription
   (₹499+/month as of Sept 2026 — see groww.in/trade-api for current
   pricing).
2. Generate an API key + secret (or a TOTP token) from the Groww Cloud
   API Keys page.
3. Set `MARKET_DATA_PROVIDER=groww`, `GROWW_API_KEY=...`,
   `GROWW_API_SECRET=...` in `.env`.
4. Fill in the symbol-mapping table in `groww_provider.py:_map_symbol` —
   Groww's API addresses instruments as (exchange, segment,
   trading_symbol), not the `.NS`/`.BO`-suffixed symbols this codebase
   uses internally, and the exact mapping depends on which symbols from
   `symbol_universe.py` you want live on Groww's feed.

**Before relying on this for a paying customer**: Groww's API is built
around one person's own account trading their own money — the
auth model is "this account's key/secret," not a service-account or
partner-API model. Whether their terms of service permit using that feed
to power a multi-tenant product serving *other* people's watchlists (as
opposed to your own personal algo trading) is a question to put to Groww
directly before shipping this path to customers — this codebase can wire
up the integration, but it can't answer a licensing/ToS question on your
behalf.

## Adding another provider

Implement `MarketDataProvider.fetch_quote(symbol) -> dict` (see
`base.py` for the exact return shape) in a new module under this
package, then add one branch to `market_data/__init__.py:get_provider()`.
Nothing else in the codebase needs to change — that's the point of the
abstraction.
