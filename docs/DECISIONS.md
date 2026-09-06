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
symbol universe for the NL-add feature, and moving the cache/pub-sub
layer to real Redis once there's more than one backend process to justify
it.
