"""
Turns already-correct, pre-computed deltas into a short natural-language
catch-up summary via Groq.

The load-bearing design decision: the LLM is handed structured, verified
numbers (price_change_pct, z_score, volume_change_pct — all computed by
diff_engine.py with plain arithmetic) and asked only to phrase them, not
to compute or guess them. It is explicitly instructed not to invent any
number that isn't in the input. This is what prevents the classic
hackathon failure mode of an LLM confidently hallucinating a price.

If GROQ_API_KEY is missing or the call fails/times out, this falls back
to a deterministic, still-useful plain-text summary built from the same
deltas — the feature degrades gracefully instead of breaking the page.
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("pulse.digest_generator")

SYSTEM_PROMPT = """You are writing a short "catch-up" market digest for a user \
returning to their watchlist. You will be given a JSON list of pre-computed, \
verified deltas — one per stock.

Rules:
- Only mention stocks where "significant" is true, unless none are significant \
(in that case, say nothing much changed).
- NEVER invent a number. Only use the numbers given to you.
- Write 1 short sentence per significant stock, plain English, no jargon.
- If volume_change_pct is notably large, mention it as a likely driver of attention.
- Keep the whole digest under 80 words.
- Tone: a sharp, concise analyst friend texting you, not a data report.
"""


def _fallback_digest(deltas: list[dict]) -> str:
    significant = [d for d in deltas if d.get("significant")]
    if not significant:
        return "Nothing significant changed across your watchlist since you last checked."

    lines = []
    for d in significant:
        pct = d.get("price_change_pct")
        pct_str = f"{pct:+.2%}" if pct is not None else "an unclear amount"
        stale_note = " (data delayed)" if d.get("stale") else ""
        lines.append(f"{d['symbol']} moved {pct_str}{stale_note}.")
    return " ".join(lines)


def generate_digest(deltas: list[dict]) -> tuple[str, bool]:
    """Returns (digest_text, ai_generated: bool)."""
    if not settings.GROQ_API_KEY:
        logger.info("GROQ_API_KEY not set — using deterministic fallback digest")
        return _fallback_digest(deltas), False

    try:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)
        # Only send the fields the model actually needs — no PII, no raw prices
        # it isn't allowed to restate arithmetic on.
        payload = [
            {
                "symbol": d["symbol"],
                "significant": d["significant"],
                "price_change_pct": d["price_change_pct"],
                "volume_change_pct": d["volume_change_pct"],
                "z_score": d["price_z_score"],
                "stale": d.get("stale", False),
            }
            for d in deltas
        ]
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": str(payload)},
            ],
            temperature=0.4,
            max_tokens=150,
            timeout=8,
        )
        text = completion.choices[0].message.content.strip()
        if not text:
            raise ValueError("Empty response from Groq")
        return text, True
    except Exception as exc:  # noqa: BLE001 — external API boundary, must never crash the request
        logger.warning("Groq digest generation failed, falling back: %s", exc)
        return _fallback_digest(deltas), False
