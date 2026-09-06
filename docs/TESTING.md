# Testing

## What's covered by the automated suite (`pytest`, runs in CI)

53 tests, ~71% line coverage of `app/`, in two layers:

- **Unit tests** (`test_significance.py`, `test_diff_engine.py`,
  `test_nl_intent.py`, `test_alert_service.py`, `test_chat_service.py`):
  call service functions directly against an isolated in-memory SQLite
  session. These are where the actual product logic gets proven — the
  volatility-relative significance math, the per-user watermark diffing,
  the alert de-duplication, the anti-hallucination LLM-fallback paths.

- **API integration tests** (`test_api_auth.py`, `test_api_watchlists.py`,
  `test_api_chat.py`, `test_api_market.py`): drive the real FastAPI app
  through `TestClient` — real HTTP requests, real dependency injection,
  real middleware (rate limiting, security headers, request-ID logging) —
  against an isolated in-memory DB. This is the layer that catches wiring
  bugs the unit tests structurally can't: a wrong status code, an
  authorization boundary that leaks another user's data, a response
  model missing a field. Two real bugs were caught and fixed by writing
  these tests (see `docs/DECISIONS.md`): a SQLite autoincrement
  incompatibility that would have crashed the scheduler on its first
  multi-symbol poll, and an alert de-duplication check that silently
  never engaged for a user's first significant view.

Run locally:

```bash
cd backend
source venv/bin/activate
pytest -q --cov=app --cov-report=term-missing
```

## What's intentionally NOT covered by the automated suite

- **`app/services/market_data/auto_provider.py` and `groww_provider.py`
  (0% coverage)**: both make real outbound network calls to yfinance,
  NSE, or Groww's API. Unit-testing them meaningfully means either
  mocking the network (testing the mock, not the integration) or hitting
  the real services from CI (flaky, rate-limited, and — for Groww —
  requires a paid account). These were instead verified interactively
  during development: the "auto" provider's circuit-breaker fallback
  chain was exercised against this sandbox's restricted network (which
  correctly produces the "both sources failed, raise cleanly" path every
  time), and the Groww provider's fail-fast behavior without credentials
  was confirmed directly.

- **`app/ws/prices.py` (31% coverage)**: the WebSocket price-streaming
  endpoint. `TestClient` can drive WebSocket connections, but doing so
  meaningfully here means also driving the scheduler and cache together,
  which is more end-to-end-test territory than unit test. Manually
  verified during development (see architecture notes); a real
  WebSocket test is a reasonable next addition.

- **`app/services/scheduler.py`'s `poll_once` (43% coverage)**: the parts
  not covered are the actual network-fetch-and-persist loop, for the same
  reason as the market-data providers above. `alert_service.py`, which it
  calls into, IS fully covered — the polling loop itself is a thin
  orchestration layer around already-tested pieces.

- **Frontend**: no automated component/unit tests yet. The frontend was
  instead verified with real, driven browser sessions (Playwright against
  a live dev server) at each feature milestone — signup/login, watchlist
  CRUD, the sparkline chart, natural-language add, and the chat widget
  were each clicked through and screenshotted, not just built and
  assumed to work. Adding Vitest + React Testing Library for the
  component layer is a reasonable next step before a large frontend
  refactor, but wasn't the highest-value use of time versus the backend
  gaps above.

## CI

`.github/workflows/ci.yml` runs the full backend suite against a real
Postgres + Redis (service containers, not SQLite/mocks) on every push and
PR to `main`, plus an Alembic migration + full app boot smoke test, and
the frontend's lint + type-check + build. See that file for specifics.
