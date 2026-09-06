# Decisions — the "why" behind every non-obvious call

This is the document to open before the Q&A round. Every entry below is a
place where a different, equally valid choice existed, and this is the
reasoning for the one that was made.

### Why a volatility-relative significance model instead of a fixed % threshold?
A fixed threshold treats every stock identically, which means it either
buries you in noise for genuinely volatile stocks or misses real signal
in quiet ones. Expressing today's move as a z-score against the symbol's
own rolling volatility makes "significant" mean the same thing — a
statistically unusual day — for every stock, regardless of how choppy it
normally is. Proven in `tests/test_significance.py`: an identical +2% move
is flagged for a quiet stock and correctly ignored for a volatile one.

### Why per-user watermark, not per-device?
Two devices for the same user seeing different "unseen" states would mean
marking a move as seen on your phone but still flagging it stale on your
laptop — which contradicts what the user actually wants to know ("have I
personally seen this yet"). A per-user watermark is the more honest
product decision, even though per-device would have been marginally
easier to reason about technically.

### Why is `mark-seen` an explicit endpoint instead of updating on every GET?
If viewing a watchlist silently updated the watermark, the delta would be
erased the instant the page loads — before the user has actually read it.
Making it an explicit action (or an explicit call after the UI has
rendered the delta) means the signal survives long enough to be seen.

### Why SQLite by default instead of Postgres?
For a 72-hour solo build and for a judge doing a clean clone, zero
external setup matters more than production-grade concurrency. All
access goes through SQLAlchemy, so switching `DATABASE_URL` to a Postgres
connection string is the only change needed to move to Postgres — nothing
in the application code is SQLite-specific.

### Why an in-process cache instead of Redis?
The blueprint's scalability answer ("shared fetch, per-user diff") is
about the *shape* of the caching layer, not the specific technology. With
a single backend process, an in-memory dict is correct, fast, and adds
zero deployment risk. `app/services/cache.py` is deliberately written
with a Redis-shaped interface (`get_latest`/`set_latest`/`subscribe`) so
that swapping in `redis.asyncio` when there's a second backend process to
share state with is a contained, mechanical change.

### Why `Base.metadata.create_all()` instead of Alembic migrations?
The schema has one meaningful evolution path so far (this initial
design), and for a 72-hour build, hand-rolling a migration history for a
schema that hasn't shipped yet is complexity with no near-term payoff.
Alembic is the documented next step once the schema needs to evolve under
real data (see `requirements.txt` — it's not installed, to keep that
decision honest rather than half-done).

### Why no market holiday calendar?
`is_market_open_now()` checks NSE trading hours and weekday, but not
exchange holidays. A wrong "closed" label on a holiday only affects the
phrasing of the staleness badge, never the correctness of the price or
the significance math — an acceptable, explicitly-stated gap for the
time budget, not a silent one.

### Why does the LLM never see raw prices, only pre-computed deltas?
Letting an LLM compute or restate a financial number from context is the
single most common way AI-in-finance demos fail live — a plausible-looking
hallucinated figure is worse than no digest at all. `digest_generator.py`
hands Groq only already-verified percentages and z-scores and instructs
it to phrase them, never calculate them. The system prompt explicitly
forbids inventing a number, and the code path used to build the payload
never includes raw price fields the model could echo back incorrectly.

### Why is the natural-language "add to watchlist" constrained to a fixed symbol universe?
Same principle as the digest generator: letting an LLM freely name a
ticker it "knows" risks a plausible-looking but wrong or delisted symbol
being silently added to someone's watchlist. `nl_intent.py` gives the
model (or the keyword fallback, if no Groq key is set) a closed list of
~30 curated NSE symbols and instructs it to choose only from that list —
then re-validates the model's output against that same list in code
before anything touches the database. The honest trade-off: the feature
can only ever suggest symbols from that curated set, not arbitrary
tickers. Expanding the universe, or replacing it with a real symbol
search API, is the documented next step.

### Why a hand-rolled SVG sparkline instead of the lightweight-charts library?
A 30-point trend line in a table cell doesn't need a full charting
engine's pan/zoom/crosshair/scale machinery — it needs a polyline. A
~20-line inline SVG component has no container-sizing edge cases inside a
table row and is trivially themeable, whereas wiring a full chart library
into a table cell for a sparkline would be complexity spent on the wrong
problem. `lightweight-charts` is still the right choice for a dedicated,
full-size price chart view, which is a reasonable next addition.

### What would be built next with more time?
In priority order: a small market-holiday calendar, a lightweight
news-correlation hint on the digest (explicitly hedged as "likely
driver," never asserted as causal), a full per-symbol price chart view
(using `lightweight-charts`, now that it's justified), a larger/searchable
symbol universe for the NL-add feature.

---

## Production-hardening pass (post-hackathon)

The entries above describe the original 72-hour hackathon build. Everything
below documents the deliberate decisions made turning that into something
closer to what you'd actually hand to a paying customer — including two
real bugs the hardening work surfaced and fixed.

### Why refresh tokens (opaque, server-side, hashed) instead of just longer-lived JWTs?
A stateless JWT can't be revoked early — if one leaks, it's valid until it
naturally expires no matter what you do. The fix is a short-lived (30 min)
access token for cheap per-request verification, plus a long-lived (30
day) opaque refresh token stored server-side as a SHA-256 hash (never the
raw value — same principle as password hashing). This is what makes
logout, "log out everywhere," and revoke-on-password-reset actually work,
not just cosmetically clear a cookie.

### Why rotate the refresh token on every use, and revoke everything on reuse?
Rotation means a stolen refresh token is only useful once — the legitimate
client's next refresh naturally invalidates it. But that alone isn't
enough: if an attacker uses the stolen token before the legitimate client
does, the *legitimate* client's next refresh would fail with no idea why.
Detecting reuse (presenting an already-rotated-away token) and responding
by revoking every session for that user — not just the one being reused —
is what turns "something's wrong" into an actual security response
instead of a confusing dead end for the real user. Verified in
`tests/test_api_auth.py::test_refresh_token_reuse_revokes_the_new_token_too`.

### Why did the multi-symbol scheduler poll never actually get exercised until now?
Found while writing `tests/test_alert_service.py`: `PriceSnapshot.id` was
declared as a plain `BigInteger` primary key. SQLite only auto-assigns a
primary key value for a column declared as exactly `INTEGER` — a `BIGINT`
primary key on SQLite silently does *not* get rowid-alias behavior, so
inserting more than one row in a single flush (exactly what
`scheduler.poll_once()` does the moment two or more symbols are being
polled in the same cycle) raised a `NOT NULL constraint failed` error. It
went unnoticed through the entire hackathon build because no test and no
manual demo ever had two *different* symbols land in the cache/DB in the
same poll cycle. Fixed with SQLAlchemy's documented cross-dialect idiom —
`BigInteger().with_variant(Integer, "sqlite")` — which keeps full BIGINT
range on Postgres while making SQLite's autoincrement actually work.
Regression-tested directly in `test_alert_service.py`.

### Why does alert de-duplication use a `-1` sentinel for "no baseline yet"?
Also found while testing: the first draft's de-dup check was `state.
last_alerted_price is not None and baseline is not None and ...` — but a
user's very first significant view of a symbol has `last_seen_price =
None` by definition (there's nothing to compare against yet). That guard
meant the "already alerted for this baseline" check could never match a
first-view alert, so it would silently re-send an email every single poll
cycle (every 45 seconds) until the user viewed the symbol. Since a real
price is never ≤ 0, using `-1.0` as an explicit sentinel for "no baseline"
lets that case de-duplicate through the exact same code path as every
other baseline, instead of needing a separate branch. Both the original
bug and the fix are documented in the code comment right next to the
check, not just here — the point is to stop someone "cleaning up" that
sentinel back into the broken version.

### Why Alembic now, having previously decided against it?
The earlier decision was explicitly "not yet, while the schema hasn't
shipped." That condition no longer holds once real customer data could
exist. `alembic/env.py` is wired to the app's own `Settings.DATABASE_URL`
and `Base.metadata`, so the same migration runs correctly against SQLite
in dev and Postgres in production. `app/main.py` now only auto-creates
tables via `create_all()` when `ENVIRONMENT != "production"` — in
production, a missed migration should fail loudly (the app boots against
a schema it doesn't recognize), not get silently patched over.

### Why does `CACHE_BACKEND=redis` also need to handle cross-process pub/sub, not just shared storage?
Once there's more than one backend instance, two things break with the
old in-memory cache: (1) each instance polls prices independently
(duplicate API calls, and users get different answers depending which
instance served them), and (2) a WebSocket client connected to instance B
never hears about a price instance A just fetched. `app/services/cache.py`'s
Redis backend fixes both — a Redis hash for storage (any instance's
`HGETALL` sees every symbol any instance has ingested) plus a Redis
pub/sub channel that every instance's `AsyncBroadcaster` subscribes to, so
a quote published by any instance reaches every instance's WebSocket
clients. Verified directly (not just unit-tested) against a real local
Redis: a message published by a simulated "other process" was received by
this process's broadcaster.

### Why keep `MARKET_DATA_PROVIDER=auto` (yfinance + NSE) as the default even now?
It's still the only *free* option, and it's still not something you'd
want a paying customer's production traffic solely depending on (no SLA,
no commercial license, undocumented NSE endpoint). Rather than pretend
otherwise, the provider abstraction (`app/services/market_data/`) makes
switching to a licensed source — Groww's own Trading API is wired up as a
real, working option, not a stub — a config change (`MARKET_DATA_PROVIDER`
+ two env vars) instead of a rewrite. The honest caveat, stated in
`market_data/README.md`: Groww's API auth model is built around one
person's own trading account, and whether its terms permit powering a
multi-tenant product serving other people is a question for Groww
directly, not something resolved in code.

### Why a chatbot grounded in the same verified deltas, with an explicit "not a financial advisor" refusal?
A watchlist chatbot that quietly starts giving "should I buy this" answers
is both an inaccurate product (LLMs are not reliable predictors of stock
prices) and a real legal exposure (unlicensed investment advice). Same
anti-hallucination pattern as the digest and NL-add features — the LLM
sees only pre-computed, correct deltas and is explicitly instructed to
decline advice questions rather than answer them "helpfully." The
deterministic fallback (no Groq key, or the API call fails) never faces
this risk at all, since it only ever echoes the verified numbers back.

### Why soft-delete for account deletion, and why does it still clear chat history?
A hard `DELETE FROM users` would need to either cascade-delete or orphan
every row that references `user_id` (watchlists, digests, refresh
tokens) — fine for a hobby project, riskier once there's a support
process or a legal hold that might need those records intact. Soft-delete
(`is_active=False`, email scrubbed to a non-guessable placeholder, every
session revoked) achieves the practical goal — the account is
unreachable and unusable within milliseconds of the request — while
leaving a real hard-delete-after-N-days purge job as a documented,
explicit next step rather than something silently half-done. Chat history
is the one exception deleted outright rather than left in place: it's
more likely to contain free-form personal content than a structured
watchlist ever would.
