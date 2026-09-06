"""
In-process quote cache.

Design note (say this out loud in the demo, not hide it): this stands in
for Redis. The interface (get/set/publish) is deliberately Redis-shaped —
get_latest / set_latest / subscribe — so swapping this module for a real
`redis.asyncio` client is a drop-in change, not a rewrite. For a solo
72-hour build with a single backend process, an in-memory dict is the
honest choice: it is correct, it is testable, and adding a Redis
dependency here would be complexity with no payoff until there's a second
backend process to share cache with.
"""
import asyncio
import threading
from typing import Callable

_lock = threading.Lock()
_store: dict[str, dict] = {}
_subscribers: list[Callable[[str, dict], None]] = []


def set_latest(symbol: str, quote: dict) -> None:
    with _lock:
        _store[symbol] = quote
    for callback in list(_subscribers):
        try:
            callback(symbol, quote)
        except Exception:
            # A broken subscriber must never take down ingestion.
            pass


def get_latest(symbol: str) -> dict | None:
    with _lock:
        return _store.get(symbol)


def all_latest() -> dict[str, dict]:
    with _lock:
        return dict(_store)


def subscribe(callback: Callable[[str, dict], None]) -> None:
    _subscribers.append(callback)


class AsyncBroadcaster:
    """Bridges the sync cache callbacks into asyncio queues for WebSocket clients."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    def register(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        return q

    def unregister(self, q: asyncio.Queue) -> None:
        if q in self._queues:
            self._queues.remove(q)

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, symbol: str, quote: dict) -> None:
        for q in list(self._queues):
            loop.call_soon_threadsafe(q.put_nowait, {"symbol": symbol, "quote": quote})


broadcaster = AsyncBroadcaster()
