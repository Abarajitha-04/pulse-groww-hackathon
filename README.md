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

### Quick start (local dev, zero external services)

```bash
# backend
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # defaults work out of the box (SQLite, no Groq key needed)
alembic upgrade head            # creates the schema — see docs/DEPLOYMENT.md
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend
npm install
cp .env.example .env            # points at http://localhost:8000 by default
npm run dev
```

Backend runs at `http://localhost:8000`, frontend at
`http://localhost:5173`. Add a `GROQ_API_KEY` in `backend/.env` to enable
the AI digest, natural-language watchlist add, and chat assistant —
without it, all three still work, using deterministic fallbacks built
from the same verified data.

### Docker (production-shaped local stack)

```bash
docker compose up --build
```

Runs Postgres + Redis + backend (with `ENVIRONMENT=production`
guardrails on) + frontend (nginx), with `alembic upgrade head` run
automatically as a one-shot step before the backend starts. See
`docs/DEPLOYMENT.md` for what this validates and its one known
limitation (this sandbox's own network policy couldn't pull Docker Hub
images to test the build itself — the app/migration path was instead
verified directly against local Postgres + Redis; see that doc for the
specifics).

### Running the tests

```bash
cd backend
source venv/bin/activate
pytest -q --cov=app --cov-report=term-missing
```

57 tests — unit tests for the significance model, diff engine, alert
de-duplication, and chat/NL-intent fallback logic, plus full HTTP-layer
integration tests (auth flow including refresh-token rotation and reuse
detection, watchlist CRUD and authorization boundaries, chat, market
data, account export/deletion) driven through FastAPI's `TestClient`
against a real (if in-memory) database — not mocks. ~71% line coverage;
see `docs/TESTING.md` for exactly what's covered, what's deliberately
not, and why.

## A note on live data

Symbol prices come from `yfinance` (primary) with an NSE India public
endpoint as a documented fallback (`app/services/price_fetcher.py`). Both
need normal outbound internet access — some sandboxed/offline
environments block this, in which case the app still runs correctly and
shows an honest "awaiting data" / stale state rather than crashing or
fabricating a price. This is the resilience behaviour described above,
not a bug.

## What's implemented vs. deliberately cut

**Core product (the original hackathon build):** auth, multi-watchlist
CRUD, symbol-centric price ingestion with primary/fallback sources and a
circuit breaker, the rolling-volatility significance model, the per-user
diff engine, the AI catch-up digest with graceful fallback, live
WebSocket price updates with a polling fallback, staleness/market-closed
handling, per-symbol sparkline trend charts, and natural-language "add to
watchlist" grounded against a fixed, curated symbol universe.

**Production hardening (added after the hackathon submission):**
- Real auth: short-lived JWT access tokens + revocable, rotating refresh
  tokens with reuse detection, logout / logout-everywhere, password
  reset, rate limiting on auth endpoints, security headers.
- Postgres support via Alembic migrations (SQLite stays the zero-setup
  dev default).
- A real Redis cache/pub-sub backend for running more than one backend
  instance correctly (`CACHE_BACKEND=redis`).
- Docker + docker-compose for backend, frontend, Postgres, and Redis.
- CI (GitHub Actions): backend tests against real Postgres + Redis, an
  Alembic migration + app-boot smoke test, and frontend lint/build.
- Structured JSON logging with request-ID correlation, an optional
  Sentry hook, and liveness/readiness health endpoints.
- Email alerts for significant moves, with de-duplication so a single
  continuous move doesn't spam the same alert every poll cycle.
- A watchlist chat assistant (Groq-backed, same anti-hallucination
  pattern as the digest — and explicitly refuses to give investment
  advice).
- A pluggable market-data provider abstraction — the free yfinance/NSE
  path stays the default, with Groww's own Trading API wired up as a
  real (if not free) licensed alternative.
- 53 additional tests (unit + full HTTP-layer integration), catching two
  real bugs along the way — see `docs/DECISIONS.md`'s "Production-
  hardening pass" section.
- Account data export and account deletion (soft-delete, session
  revocation, chat history cleared), plus draft Terms/Privacy pages.

**Still deliberately not done, and why** (see `docs/DECISIONS.md` and
`docs/TESTING.md` for the full reasoning on each): a market holiday
calendar; news correlation on the digest; a larger/searchable symbol
universe for NL-add; frontend component tests (verified instead via
driven Playwright browser sessions at each milestone); and — the biggest
one — nothing here replaces getting a real lawyer to review the Terms/
Privacy pages, or negotiating an actual commercial market-data contract,
before charging real customers money.

## Architecture

See `docs/ARCHITECTURE.md` for the full diagram and component breakdown,
and `docs/DEPLOYMENT.md` for how to actually run this in production.

```
backend/          FastAPI, SQLAlchemy, the diff/significance engine, Groq digest + chat
frontend/         React + TypeScript + Vite + Tailwind
docs/             Architecture, deployment, testing, and the reasoning behind every non-obvious decision
docker-compose.yml Local stack mirroring production topology (Postgres + Redis)
.github/workflows/ CI: tests against real Postgres/Redis, migration check, frontend build
```

## Tech stack

FastAPI · SQLAlchemy · PostgreSQL (SQLite for zero-setup dev) · Alembic ·
Redis · APScheduler · slowapi · yfinance (Groww Trading API as a licensed
alternative) · Groq (Llama 3.1) · Sentry (optional) · React 19 ·
TypeScript · Vite · TanStack Query · Zustand · Tailwind CSS · native
WebSockets · Docker.

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
