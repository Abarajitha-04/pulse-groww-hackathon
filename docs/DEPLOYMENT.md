# Deployment guide

This doc covers what's needed to run Pulse as a real, standing service
rather than a local dev instance. It's written to be filled in
incrementally as each production-hardening piece lands — see
`docs/DECISIONS.md` for the reasoning behind each choice.

## 1. Database: SQLite (dev) → Postgres (production)

SQLite is the zero-setup default so a fresh clone runs immediately. For
anything with more than one person using it concurrently, switch to
Postgres:

1. Provision a Postgres instance (Supabase, Neon, RDS, or your own).
2. Set `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname` in
   `.env` (or your platform's env var config).
3. Run the migration as a deploy step, **before** starting the app:
   ```bash
   alembic upgrade head
   ```

Schema changes from here on are made by editing `app/models/models.py`
and generating a new migration:

```bash
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/ before committing —
# autogenerate is a good first draft, not a guarantee, especially for
# column renames (it will see those as drop+add and lose data unless
# you edit the migration to an ALTER ... RENAME by hand)
alembic upgrade head
```

`app/main.py` only auto-creates tables via `Base.metadata.create_all()`
when `ENVIRONMENT != "production"`. In production, Alembic is the single
source of truth for schema — this is deliberate: it means a missed
migration fails loudly (the app boots against a schema it doesn't
recognize) instead of silently patching itself.

## 2. Required production environment variables

Setting `ENVIRONMENT=production` turns on a startup check
(`app/main.py:_validate_production_config`) that refuses to boot if any
of these are still at their insecure dev defaults:

| Variable | Requirement in production |
|---|---|
| `SECRET_KEY` | A real random secret, 32+ bytes (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `DATABASE_URL` | Postgres, not SQLite |
| `CORS_ORIGINS` | Your real frontend origin(s) only — no `localhost` |
| `CACHE_BACKEND` | `redis`, not `memory`, once you run more than one backend instance |

See `.env.example` for the full variable list (SMTP, Groq, Sentry, rate
limits, market data provider).

## 3. Running more than one backend instance

The in-memory cache (`CACHE_BACKEND=memory`) and the APScheduler polling
job both assume a single process. Running multiple instances behind a
load balancer without addressing this means: each instance polls prices
independently (wasted API calls, and users can see different "last
seen" states depending which instance served them), and WebSocket
subscribers on one instance never hear about a price picked up by
another. Set `CACHE_BACKEND=redis` (see `app/services/cache.py`) before
scaling horizontally, and run the scheduler on exactly one instance
(a `WORKER_ROLE=scheduler` style env flag, or a separate small
always-one-replica deployment, is the usual fix).

## 4. Containers

`docker-compose.yml` at the repo root runs the backend, frontend, and a
Postgres + Redis pair — the same topology as production, so integration
issues (a migration that doesn't apply cleanly, a CORS misconfiguration,
a cache backend that isn't actually wired up) surface locally instead of
in prod. `docker compose up --build` builds all four images, runs the
one-shot `migrate` service to completion, then starts `postgres`,
`redis`, `backend` (`ENVIRONMENT=production`, so the same startup
guardrails from §2 apply here too), and `frontend` (nginx serving the
Vite build) with health-check-gated `depends_on` ordering.

Both Dockerfiles are multi-stage (a build stage with the full toolchain,
a slim runtime stage with only what's needed to run) and the backend
image drops root via a dedicated `pulse` user. `alembic upgrade head`
runs as its own `migrate` service rather than inside the backend
container's `CMD`, deliberately — baking it into every container start
means N replicas of the backend race to apply the same migration
concurrently on a scale-up.

*Verification note:* this sandbox's network egress blocks Docker Hub
image pulls, so the actual `docker build`/`docker compose up` couldn't
be exercised end-to-end here. What *was* verified directly against
locally-installed Postgres 16 and Redis (i.e. exactly what's inside
those images, without Docker's packaging around it): `alembic upgrade
head` applying the real schema to Postgres, and the full app — booted
with `ENVIRONMENT=production`, `DATABASE_URL` pointed at Postgres, and
`CACHE_BACKEND=redis` — correctly serving signup/login/watchlist-create
requests with data persisting in Postgres and the Redis-backed cache's
cross-process pub/sub fan-out confirmed working. Run `docker compose up
--build` in an environment with normal internet access to validate the
container packaging itself before a first production deploy.

## 5. CI

See `.github/workflows/` once Task #20 lands: lint + test on every push,
so a broken build never reaches `main`.
