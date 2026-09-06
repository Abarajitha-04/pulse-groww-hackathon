# Architecture

```
                     ┌────────────────────────┐
                     │   Price Fetcher (job)   │  every POLL_INTERVAL_SECONDS,
                     │  yfinance -> NSE fallback│ once per DISTINCT watched symbol
                     └───────────┬─────────────┘ (not once per user)
                                 │ writes
                                 ▼
                     ┌────────────────────────┐
                     │  In-process cache:      │  keyed by symbol,
                     │  latest quote + ts      │  Redis-shaped interface
                     └───────────┬─────────────┘
                                 │ publish on update
                                 ▼
                     ┌────────────────────────┐
                     │  price_snapshots (DB)   │  append-only, source + timestamp
                     │  (diff engine's history)│
                     └───────────┬─────────────┘
                                 │
                ┌────────────────┴─────────────────┐
                ▼                                   ▼
    ┌───────────────────────┐          ┌──────────────────────────┐
    │   Diff Engine           │          │   WebSocket Fanout        │
    │  per-user watermark vs  │          │  live ticks to open tabs  │
    │  current -> significance│          └──────────────────────────┘
    └───────────┬─────────────┘
                ▼
    ┌───────────────────────┐
    │  Digest Generator (Groq)│  facts -> prose, deterministic fallback if no key/failure
    └───────────┬─────────────┘
                ▼
    ┌───────────────────────┐
    │   FastAPI REST + WS    │
    └───────────┬─────────────┘
                ▼
    ┌───────────────────────┐
    │   React SPA             │
    └───────────────────────┘
```

## The one sentence that matters

**The fetch layer is symbol-centric; the diff layer is user-centric.**

Fetching a quote is the only step that costs an external API call, so it
happens once per symbol per poll cycle no matter how many users are
watching it (`app/services/price_fetcher.py`, orchestrated by
`app/services/scheduler.py`). Computing *your* delta since *your* last
visit is pure arithmetic against your own watermark row
(`user_symbol_state`) and a short slice of cached history — cheap enough
to run on every request, for every user, without touching the network.

## Components

- **`app/services/price_fetcher.py`** — primary (`yfinance`) + secondary
  (NSE India public endpoint) sources, each behind its own per-symbol
  circuit breaker (3 consecutive failures trips it, 120s cooldown before
  a half-open retry). A symbol with a delisted or broken feed never
  blocks polling for the rest of the watchlist.
- **`app/services/cache.py`** — the shared "latest quote" store. Built
  with a Redis-shaped interface (`get_latest` / `set_latest` / `subscribe`)
  so swapping in `redis.asyncio` later is a drop-in change, not a
  rewrite. Kept in-process here because a single backend instance has no
  second process to share cache with — see `docs/DECISIONS.md`.
- **`app/services/significance.py`** — the core differentiator. Computes
  a z-score of today's move against the symbol's own rolling volatility
  rather than a fixed percentage threshold.
- **`app/services/diff_engine.py`** — reads the shared cache + the
  requesting user's watermark + recent history, and returns a structured,
  explainable delta. Also owns market-hours detection and staleness
  suppression (a stale quote is never presented as a confirmed signal).
- **`app/services/digest_generator.py`** — narrates verified deltas via
  Groq; falls back to a deterministic summary built from the same
  numbers if no API key is set or the call fails.
- **`app/services/scheduler.py`** — APScheduler job that polls every
  distinct symbol across all watchlists once per cycle and fans updates
  out over both the DB (audit trail) and the in-process pub/sub used by
  the WebSocket route.
- **`app/ws/prices.py`** — live tick stream; the frontend is built to
  fall back to its 15s polling refetch if the socket never connects, so
  the app is fully usable without WebSocket support.

## Database schema

See the model definitions in `backend/app/models/models.py`. The table
worth reading closely is `user_symbol_state` — it's what turns "return
later and see what changed" into a real, queryable feature instead of a
client-side trick.
