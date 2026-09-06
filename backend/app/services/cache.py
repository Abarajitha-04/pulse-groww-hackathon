"""
Quote cache + pub/sub, with two interchangeable backends behind the same
module-level function interface (get_latest / set_latest / all_latest /
subscribe / broadcaster) so callers never know or care which one is active:

  - "memory" (CACHE_BACKEND=memory, the dev/demo default): a plain
    in-process dict. Correct and simple for exactly one backend process.
  - "redis" (CACHE_BACKEND=redis): a real Redis hash for storage (every
    instance's HGETALL sees every symbol any instance has ingested) plus
    a Redis pub/sub channel for fan-out (a price picked up by instance A
    reaches WebSocket clients connected to instance B). This is what
    makes running more than one backend process behind a load balancer
    actually correct — see docs/DEPLOYMENT.md §3.

The backend is chosen once, at import time, from settings.CACHE_BACKEND.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime
from typing import Callable

from app.core.config import settings

logger = logging.getLogger("pulse.cache")


class AsyncBroadcaster:
    """Bridges cache-update callbacks into asyncio queues for WebSocket
    clients. Holds a reference to the running event loop so both the
    scheduler (same process, memory backend) and the Redis pub/sub
    listener thread (possibly notifying about another process's
    ingestion) can push updates into it without re-plumbing the loop
    through every call site."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        return q

    def unregister(self, q: asyncio.Queue) -> None:
        if q in self._queues:
            self._queues.remove(q)

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop | None, symbol: str, quote: dict) -> None:
        target_loop = loop or self._loop
        if target_loop is None:
            return
        for q in list(self._queues):
            target_loop.call_soon_threadsafe(q.put_nowait, {"symbol": symbol, "quote": quote})


broadcaster = AsyncBroadcaster()

_subscribers: list[Callable[[str, dict], None]] = []


def subscribe(callback: Callable[[str, dict], None]) -> None:
    """Local, same-process callback hook (used by the memory backend only —
    a Redis-backed multi-process deployment should use the pub/sub channel
    directly for cross-process notification, which broadcaster already
    handles for the WebSocket case)."""
    _subscribers.append(callback)


class _MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, dict] = {}

    def set_latest(self, symbol: str, quote: dict) -> None:
        with self._lock:
            self._store[symbol] = quote
        for callback in list(_subscribers):
            try:
                callback(symbol, quote)
            except Exception:
                # A broken subscriber must never take down ingestion.
                logger.exception("Cache subscriber callback raised for %s", symbol)

    def get_latest(self, symbol: str) -> dict | None:
        with self._lock:
            return self._store.get(symbol)

    def all_latest(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._store)


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _decode_quote(raw: str) -> dict:
    quote = json.loads(raw)
    if quote.get("exchange_ts"):
        quote["exchange_ts"] = datetime.fromisoformat(quote["exchange_ts"])
    return quote


class _RedisBackend:
    HASH_KEY = "pulse:quotes"
    CHANNEL = "pulse:quote_updates"

    def __init__(self, redis_url: str) -> None:
        import redis  # local import: keeps `redis` optional when CACHE_BACKEND=memory

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._redis.ping()  # fail fast at boot, not on the first request
        self._start_subscriber_thread()

    def set_latest(self, symbol: str, quote: dict) -> None:
        payload = json.dumps(quote, default=_json_default)
        self._redis.hset(self.HASH_KEY, symbol, payload)
        self._redis.publish(self.CHANNEL, json.dumps({"symbol": symbol, "quote": quote}, default=_json_default))

    def get_latest(self, symbol: str) -> dict | None:
        raw = self._redis.hget(self.HASH_KEY, symbol)
        return _decode_quote(raw) if raw else None

    def all_latest(self) -> dict[str, dict]:
        raw = self._redis.hgetall(self.HASH_KEY)
        return {symbol: _decode_quote(payload) for symbol, payload in raw.items()}

    def _start_subscriber_thread(self) -> None:
        def _listen() -> None:
            pubsub = self._redis.pubsub()
            pubsub.subscribe(self.CHANNEL)
            for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                    quote = envelope["quote"]
                    if quote.get("exchange_ts"):
                        quote["exchange_ts"] = datetime.fromisoformat(quote["exchange_ts"])
                    broadcaster.publish_threadsafe(None, envelope["symbol"], quote)
                except Exception:
                    logger.exception("Failed to process quote update from Redis pub/sub")

        thread = threading.Thread(target=_listen, daemon=True, name="pulse-redis-subscriber")
        thread.start()


_backend = _RedisBackend(settings.REDIS_URL) if settings.CACHE_BACKEND == "redis" else _MemoryBackend()


def set_latest(symbol: str, quote: dict) -> None:
    _backend.set_latest(symbol, quote)


def get_latest(symbol: str) -> dict | None:
    return _backend.get_latest(symbol)


def all_latest() -> dict[str, dict]:
    return _backend.all_latest()


def reset_for_tests() -> None:
    """Test-only hook: clears cached quotes and local subscribers between
    tests. Deliberately not exposed as part of the "real" cache API — it
    reaches into whichever backend is active rather than assuming the
    in-memory dict exists, so the test suite doesn't silently start
    talking to a real Redis if CACHE_BACKEND=redis is set in the test
    environment by mistake."""
    _subscribers.clear()
    if isinstance(_backend, _MemoryBackend):
        with _backend._lock:
            _backend._store.clear()
    else:
        for symbol in list(_backend.all_latest().keys()):
            _backend._redis.hdel(_backend.HASH_KEY, symbol)
