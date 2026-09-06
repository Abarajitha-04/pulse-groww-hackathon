"""
A small, curated, hardcoded universe of NSE large/mid-caps grouped by
sector, used only to ground the natural-language "add to watchlist"
feature (app/services/nl_intent.py).

Honest limitation, stated in the README and worth saying in the demo
Q&A: this is not a live sector-classification service — it's a fixed
list chosen to cover common requests within a 72-hour build. The LLM is
constrained to pick ONLY symbols from this list, specifically so it
cannot hallucinate a ticker that doesn't exist.
"""

SYMBOL_UNIVERSE: dict[str, list[tuple[str, str]]] = {
    "FMCG": [
        ("HINDUNILVR.NS", "Hindustan Unilever"),
        ("ITC.NS", "ITC"),
        ("NESTLEIND.NS", "Nestle India"),
        ("BRITANNIA.NS", "Britannia Industries"),
        ("DABUR.NS", "Dabur India"),
    ],
    "IT": [
        ("TCS.NS", "Tata Consultancy Services"),
        ("INFY.NS", "Infosys"),
        ("WIPRO.NS", "Wipro"),
        ("HCLTECH.NS", "HCL Technologies"),
        ("TECHM.NS", "Tech Mahindra"),
    ],
    "BANKING": [
        ("HDFCBANK.NS", "HDFC Bank"),
        ("ICICIBANK.NS", "ICICI Bank"),
        ("KOTAKBANK.NS", "Kotak Mahindra Bank"),
        ("AXISBANK.NS", "Axis Bank"),
        ("SBIN.NS", "State Bank of India"),
    ],
    "AUTO": [
        ("MARUTI.NS", "Maruti Suzuki"),
        ("TATAMOTORS.NS", "Tata Motors"),
        ("M&M.NS", "Mahindra & Mahindra"),
        ("BAJAJ-AUTO.NS", "Bajaj Auto"),
        ("EICHERMOT.NS", "Eicher Motors"),
    ],
    "ENERGY": [
        ("RELIANCE.NS", "Reliance Industries"),
        ("ONGC.NS", "Oil & Natural Gas Corp"),
        ("NTPC.NS", "NTPC"),
        ("POWERGRID.NS", "Power Grid Corp"),
        ("ADANIGREEN.NS", "Adani Green Energy"),
    ],
    "PHARMA": [
        ("SUNPHARMA.NS", "Sun Pharmaceutical"),
        ("DRREDDY.NS", "Dr. Reddy's Labs"),
        ("CIPLA.NS", "Cipla"),
        ("DIVISLAB.NS", "Divi's Laboratories"),
    ],
}


def all_symbols() -> list[tuple[str, str, str]]:
    """Flat (sector, symbol, name) list for prompting / keyword search."""
    return [
        (sector, symbol, name)
        for sector, entries in SYMBOL_UNIVERSE.items()
        for symbol, name in entries
    ]
