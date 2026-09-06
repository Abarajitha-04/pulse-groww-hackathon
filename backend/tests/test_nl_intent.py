from app.services.nl_intent import resolve_symbols, _keyword_fallback
from app.services.symbol_universe import all_symbols


def test_keyword_fallback_matches_sector_by_name():
    symbols, explanation = _keyword_fallback("show me IT stocks")
    assert "TCS.NS" in symbols
    assert "INFY.NS" in symbols
    assert "no ai" in explanation.lower()


def test_keyword_fallback_matches_sector_alias():
    symbols, _ = _keyword_fallback("add some banking names")
    assert "HDFCBANK.NS" in symbols


def test_keyword_fallback_respects_top_n():
    symbols, _ = _keyword_fallback("top 2 FMCG large-caps")
    assert len(symbols) == 2


def test_keyword_fallback_never_invents_a_symbol():
    """The core safety property: whatever comes back must be a real
    member of the curated universe, never a hallucinated ticker."""
    valid = {sym for _, sym, _ in all_symbols()}
    symbols, _ = _keyword_fallback("top 3 auto stocks")
    assert all(s in valid for s in symbols)


def test_resolve_symbols_falls_back_without_groq_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    symbols, explanation, ai_generated = resolve_symbols("pharma companies")
    assert ai_generated is False
    assert "DRREDDY.NS" in symbols or "SUNPHARMA.NS" in symbols


def test_no_match_returns_empty_list_not_a_guess():
    symbols, _ = _keyword_fallback("show me something totally unrelated to any sector xyzzy")
    assert symbols == []
