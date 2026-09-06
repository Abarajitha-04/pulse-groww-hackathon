# Pulse — A Watchlist That Tells You What You Missed

Built for **CODE, by Groww 2026** — theme: *Build a Smart Market Watchlist*.

## What this is

Every watchlist answers "what's the price right now." Pulse answers the
question a returning user actually has: **what changed since I last
looked, and does it deserve my attention?**

Instead of a flat price ticker, every symbol carries a per-user "last
seen" watermark. On return, a diff engine compares the current price
against that watermark using a **rolling-volatility significance model**
(not a fixed % threshold) to decide what counts as a meaningful move, and
an LLM (Groq) turns the verified, structured deltas into a short
natural-language catch-up summary — without ever inventing a number.

## Why this design

- **Significance is relative, not fixed.** A 2% move on a stock that
  normally swings 0.3%/day is real; the same 2% on a stock that swings
  4-6%/day is noise. `app/services/significance.py` computes a z-score
  against each symbol's own rolling volatility. See
  `tests/test_significance.py::test_same_pct_move_flagged_on_quiet_stock_but_not_volatile_stock`
  for the concrete proof this claim actually holds.
- **Shared fetch, per-user diff.** One polling job fetches each watched
  symbol once per cycle, cached and shared across every user watching it
  (`app/services/price_fetcher.py` + `cache.py`). The expensive part
  doesn't scale with user count — only the cheap per-user diff does.
  See `docs/ARCHITECTURE.md`.
- **Staleness and failure are first-class, visible states**, not silent
  bugs. A dead data source degrades to a clearly-labelled "delayed" badge
  instead of a confidently wrong price (`app/services/price_fetcher.py`'s
  circuit breaker, `diff_engine.py`'s staleness check).
- **The AI never invents a number.** `digest_generator.py` hands the LLM
  only pre-computed, correct deltas and asks it to phrase them — if the
  call fails or no API key is set, it falls back to a deterministic
  plain-text summary built from the same verified numbers.
- Full reasoning behind every non-obvious decision — including what was
  deliberately cut and why — is in `docs/DECISIONS.md`.

## Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # defaults work out of the box (SQLite, no Groq key needed)
PYTHONPATH=. uvicorn app.main:app --reload
```

Runs at `http://localhost:8000`. Tables are created automatically on
first run (see `docs/DECISIONS.md` for why this project skips Alembic).
Add a `GROQ_API_KEY` in `.env` to enable the AI digest — without it, the
digest endpoint still works, using a deterministic fallback summary.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env            # points at http://localhost:8000 by default
npm run dev
```

Runs at `http://localhost:5173`.

### Running the tests

```bash
cd backend
PYTHONPATH=. venv/bin/python -m pytest tests/ -v
```

17 tests covering the significance model, the diff engine, and the
natural-language intent parser — including the per-user-not-per-device
watermark isolation, the stale-data suppression behaviour, and the
safety property that the NL-add feature can never invent a ticker.

## A note on live data

Symbol prices come from `yfinance` (primary) with an NSE India public
endpoint as a documented fallback (`app/services/price_fetcher.py`). Both
need normal outbound internet access — some sandboxed/offline
environments block this, in which case the app still runs correctly and
shows an honest "awaiting data" / stale state rather than crashing or
fabricating a price. This is the resilience behaviour described above,
not a bug.

## What's implemented vs. deliberately cut

**Implemented:** auth, multi-watchlist CRUD, symbol-centric price
ingestion with primary/fallback sources and a circuit breaker, the
rolling-volatility significance model, the per-user diff engine, the AI
catch-up digest with graceful fallback, live WebSocket price updates with
a polling fallback, staleness/market-closed handling, per-symbol
sparkline trend charts, natural-language "add to watchlist" (e.g. "top 3
FMCG large-caps") grounded against a fixed, curated symbol universe so it
can never invent a ticker, and a full test suite (17 tests) for the core
logic.

**Deliberately cut for the 72-hour window** (see `docs/DECISIONS.md` for
the reasoning on each): Alembic migrations (using `create_all()` instead),
Redis (an in-process cache with a Redis-shaped interface instead — see
`app/services/cache.py`), a market holiday calendar, per-device state
sync, a live sector-classification service for the NL-add feature
(a curated ~30-symbol universe instead), and news correlation on the
digest (the one remaining stretch AI feature from the design blueprint).

## Architecture

See `docs/ARCHITECTURE.md` for the full diagram and component breakdown.

```
backend/          FastAPI, SQLAlchemy, the diff/significance engine, Groq digest
frontend/         React + TypeScript + Vite + Tailwind
docs/             Architecture + the reasoning behind every non-obvious decision
```

## Tech stack

FastAPI · SQLAlchemy · SQLite (Postgres-ready) · APScheduler · yfinance ·
Groq (Llama 3.1) · React 19 · TypeScript · Vite · TanStack Query ·
Zustand · Tailwind CSS · native WebSockets.

## Product pitch (100 words)

Pulse is a watchlist that answers "what changed since I last checked,"
not "what's the price right now." A rolling-volatility significance model
flags moves relative to each stock's own normal behaviour instead of a
fixed percentage — a 2% move means something different for a quiet stock
than a volatile one. An LLM narrates these pre-verified deltas into a
short catch-up summary, but never computes numbers itself, so it can't
hallucinate a figure. The architecture shares one price fetch per symbol
across every watcher, keeping per-user cost flat as the system scales,
with explicit, visible handling for stale, delayed, and conflicting data.
