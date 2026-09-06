"""
Watchlist assistant — a chat interface over the same verified numbers the
dashboard shows, not a general-purpose chatbot bolted onto the product.

Same anti-hallucination pattern as digest_generator.py and nl_intent.py:
the LLM is handed pre-computed, verified deltas (diff_engine's output —
plain arithmetic, no LLM involved in producing the numbers) as its ONLY
source of truth about prices, and is explicitly told never to invent a
number, a symbol, or an opinion the data doesn't support. It is also
explicitly told not to give investment advice ("should I buy/sell") — a
"smart watchlist" that quietly turns into an unlicensed financial advisor
the moment someone asks the wrong question is a real product/legal risk,
not a hypothetical one.

Falls back to a deterministic, still-useful canned response (built from
the same verified data) when GROQ_API_KEY is missing or the call fails —
the chat box degrades to "less articulate" rather than breaking.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import ChatMessage, User, Watchlist, WatchlistItem
from app.services import diff_engine

logger = logging.getLogger("pulse.chat")

MAX_HISTORY_MESSAGES = 12  # keeps the prompt small and the LLM call cheap/fast

SYSTEM_PROMPT = """You are the assistant inside "Pulse", a stock watchlist app. \
You will be given the user's current watchlist data as a JSON list of \
pre-computed, verified deltas (one per stock they track) and the recent \
conversation history.

Rules:
- Answer ONLY using the numbers in the provided JSON. NEVER invent a \
price, percentage, or figure that isn't there.
- If asked about a stock not in the provided data, say you don't have \
data for it — don't guess.
- You are NOT a financial advisor. If asked for investment advice (should \
I buy/sell/hold, price predictions, "is this a good stock"), politely \
decline and explain you can only describe what already happened, not \
predict what happens next or recommend trades.
- Keep answers short — 2-4 sentences unless the user clearly wants more detail.
- Tone: helpful, direct, a bit like a sharp analyst friend — not corporate, \
not sycophantic.
"""


def _fallback_reply(deltas: list[dict], message: str) -> str:
    significant = [d for d in deltas if d.get("significant")]
    if not deltas:
        return "You don't have any symbols on your watchlist yet — add one and I can talk you through it."
    if not significant:
        return (
            "Nothing on your watchlist has moved significantly right now. "
            "(AI chat is unavailable, so this is a plain data summary rather than a full answer to your question.)"
        )
    lines = [
        f"{d['symbol']}: {d['price_change_pct'] * 100:+.2f}% (now {d['current_price']})"
        if d.get("price_change_pct") is not None
        else f"{d['symbol']}: {d['reason']}"
        for d in significant
    ]
    return "AI chat is unavailable right now, but here's what's significant: " + "; ".join(lines)


def _gather_watchlist_context(db: Session, user: User) -> list[dict]:
    items = (
        db.query(WatchlistItem.symbol)
        .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
        .filter(Watchlist.user_id == user.id)
        .distinct()
        .all()
    )
    symbols = [row[0] for row in items]
    return [diff_engine.compute_delta_for_symbol(db, user.id, symbol) for symbol in symbols]


def generate_reply(db: Session, user: User, message: str) -> tuple[str, bool]:
    """Returns (reply_text, ai_generated). Persists both the user's message
    and the assistant's reply to ChatMessage — callers don't need to."""
    context = _gather_watchlist_context(db, user)

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    history = list(reversed(history))

    db.add(ChatMessage(user_id=user.id, role="user", content=message))
    db.commit()

    if not settings.GROQ_API_KEY:
        reply = _fallback_reply(context, message)
        ai_generated = False
    else:
        try:
            from groq import Groq

            client = Groq(api_key=settings.GROQ_API_KEY)
            payload = [
                {
                    "symbol": d["symbol"],
                    "significant": d["significant"],
                    "price_change_pct": d["price_change_pct"],
                    "current_price": d["current_price"],
                    "volume_change_pct": d["volume_change_pct"],
                    "z_score": d["price_z_score"],
                    "stale": d.get("stale", False),
                    "reason": d["reason"],
                }
                for d in context
            ]
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.append({"role": "system", "content": f"Current watchlist data: {payload}"})
            for h in history:
                messages.append({"role": h.role, "content": h.content})
            messages.append({"role": "user", "content": message})

            completion = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=300,
                timeout=8,
            )
            reply = completion.choices[0].message.content.strip()
            if not reply:
                raise ValueError("Empty response from Groq")
            ai_generated = True
        except Exception as exc:  # noqa: BLE001 — external API boundary
            logger.warning("Groq chat completion failed, falling back: %s", exc)
            reply = _fallback_reply(context, message)
            ai_generated = False

    db.add(ChatMessage(user_id=user.id, role="assistant", content=reply))
    db.commit()

    return reply, ai_generated
