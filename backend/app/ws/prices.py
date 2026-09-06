"""
Live tick stream. Clients subscribe with a comma-separated symbol list;
they receive a JSON message every time ANY watched symbol updates
(filtered server-side to the symbols they asked for), sourced from the
same shared cache the REST endpoints read — no duplicate fetching.

If the socket drops, the frontend is expected to fall back to polling
GET /market/quote/{symbol} — this is stated explicitly so it's clear the
system doesn't depend on WebSocket support to function.
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import cache

logger = logging.getLogger("pulse.ws")
router = APIRouter()


@router.websocket("/ws/prices")
async def prices_ws(websocket: WebSocket):
    await websocket.accept()
    symbols_param = websocket.query_params.get("symbols", "")
    wanted = {s.strip().upper() for s in symbols_param.split(",") if s.strip()}

    queue = cache.broadcaster.register()
    try:
        # Send current snapshot immediately so the client isn't blank
        # until the next poll cycle fires.
        for symbol, quote in cache.all_latest().items():
            if not wanted or symbol in wanted:
                await websocket.send_text(json.dumps({"symbol": symbol, "quote": _safe(quote)}))

        while True:
            item = await queue.get()
            if wanted and item["symbol"] not in wanted:
                continue
            await websocket.send_text(json.dumps({"symbol": item["symbol"], "quote": _safe(item["quote"])}))
    except WebSocketDisconnect:
        pass
    finally:
        cache.broadcaster.unregister(queue)


def _safe(quote: dict) -> dict:
    """JSON can't serialize datetimes natively."""
    out = dict(quote)
    if "exchange_ts" in out and hasattr(out["exchange_ts"], "isoformat"):
        out["exchange_ts"] = out["exchange_ts"].isoformat()
    return out
