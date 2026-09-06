"""
Natural-language "add to watchlist" (blueprint §4 / §12 stretch feature).

The load-bearing safety decision, same principle as digest_generator.py:
the LLM is constrained to choose ONLY from a fixed, curated symbol
universe (symbol_universe.py) — it is never allowed to invent a ticker.
If GROQ_API_KEY is missing or the call fails, a plain keyword-matching
fallback runs instead: also constrained to the same universe, just less
flexible about phrasing. Either path is safe; only the quality of the
match differs.
"""
from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.services.symbol_universe import SYMBOL_UNIVERSE, all_symbols

logger = logging.getLogger("pulse.nl_intent")

SYSTEM_PROMPT = """You map a user's plain-English request onto a FIXED list \
of stock symbols. You will be given the allowed universe as a JSON list of \
[sector, symbol, company_name] triples.

Rules:
- You may ONLY return symbols that appear verbatim in the given universe.
- NEVER invent a symbol that isn't in the list, even if you know a real \
ticker for a company the user mentioned.
- If the request implies a count (e.g. "top 3"), respect it; otherwise \
return all matches for the implied sector(s).
- If nothing in the universe matches, return an empty list.
- Respond with ONLY a JSON object: {"symbols": ["SYM1.NS", "SYM2.NS"], \
"explanation": "one short sentence"}. No other text.
"""


def _keyword_fallback(query: str) -> tuple[list[str], str]:
    query_lower = query.lower()
    matched_sector = None
    for sector in SYMBOL_UNIVERSE:
        if sector.lower() in query_lower:
            matched_sector = sector
            break

    # Loose aliasing for common phrasing the fixed sector names won't catch.
    aliases = {
        "IT": ["tech", "software", "it stocks"],
        "FMCG": ["consumer goods", "fmcg"],
        "BANKING": ["bank", "banks", "financial"],
        "AUTO": ["car", "cars", "automobile", "vehicle"],
        "ENERGY": ["power", "oil", "energy"],
        "PHARMA": ["pharma", "drug", "healthcare", "medicine"],
    }
    if not matched_sector:
        for sector, terms in aliases.items():
            if any(term in query_lower for term in terms):
                matched_sector = sector
                break

    if not matched_sector:
        # Last resort: match individual company names mentioned by name.
        symbols = [sym for _, sym, name in all_symbols() if name.lower() in query_lower]
        return symbols, "Matched by company name (no AI available for broader intent matching)."

    symbols = [sym for sym, _ in SYMBOL_UNIVERSE[matched_sector]]

    import re

    count_match = re.search(r"top\s+(\d+)", query_lower)
    if count_match:
        symbols = symbols[: int(count_match.group(1))]

    return symbols, f"Matched sector '{matched_sector}' by keyword (no AI available)."


def resolve_symbols(query: str) -> tuple[list[str], str, bool]:
    """Returns (symbols, explanation, ai_generated)."""
    if not settings.GROQ_API_KEY:
        symbols, explanation = _keyword_fallback(query)
        return symbols, explanation, False

    try:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)
        universe_payload = json.dumps(all_symbols())
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Universe: {universe_payload}\n\nRequest: {query}"},
            ],
            temperature=0.1,
            max_tokens=200,
            timeout=8,
        )
        raw = completion.choices[0].message.content.strip()
        parsed = json.loads(raw)
        candidate_symbols = parsed.get("symbols", [])
        explanation = parsed.get("explanation", "")

        # Hard safety filter: even though the prompt constrains the model,
        # never trust LLM output structurally — re-validate against the
        # real universe before it touches the database.
        valid_symbols = {sym for _, sym, _ in all_symbols()}
        symbols = [s for s in candidate_symbols if s in valid_symbols]

        return symbols, explanation or "Matched by AI intent parsing.", True
    except Exception as exc:  # noqa: BLE001 — external API boundary
        logger.warning("Groq NL intent parsing failed, falling back: %s", exc)
        symbols, explanation = _keyword_fallback(query)
        return symbols, explanation, False
