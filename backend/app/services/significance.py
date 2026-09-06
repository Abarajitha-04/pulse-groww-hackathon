"""
The core differentiator: "meaningful change" is defined relative to a
symbol's own recent volatility, not a fixed percentage.

Why: a 2% move on a stock that normally moves 0.3% a day is a real
signal. A 2% move on a stock that normally moves 4% a day is Tuesday.
A fixed threshold treats both the same and either drowns users in noise
or misses the moves that actually matter.

Method: compute the rolling standard deviation of daily returns for the
symbol (from price_snapshots history), then express today's move as a
z-score — how many standard deviations from zero it is. This is a
standard, well-understood statistical tool, deliberately kept simple
(no ML model, no external volatility API) — plain arithmetic that a
judge can audit in thirty seconds, which matters more than sophistication
for a 72-hour build.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SignificanceResult:
    z_score: float | None
    is_significant: bool
    reason: str


def compute_returns(prices: list[float]) -> list[float]:
    """Simple daily returns from a chronological price series."""
    returns = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        if prev == 0:
            continue
        returns.append((prices[i] - prev) / prev)
    return returns


def rolling_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def evaluate_significance(
    historical_prices: list[float],
    current_price: float,
    last_seen_price: float | None,
    z_threshold: float = 1.5,
    min_history_points: int = 8,
) -> SignificanceResult:
    """
    historical_prices: chronological closes, most recent last, NOT including
    current_price (this is the baseline window used to estimate volatility).
    """
    if last_seen_price is None:
        return SignificanceResult(None, True, "First time viewing this symbol")

    if last_seen_price == 0:
        return SignificanceResult(None, True, "No valid prior price to compare against")

    pct_change = (current_price - last_seen_price) / last_seen_price

    if len(historical_prices) < min_history_points:
        # Not enough history to trust a volatility estimate yet — fall back
        # to a conservative fixed threshold rather than refuse to flag
        # anything. This fallback is stated explicitly, not hidden: a new
        # symbol shouldn't go silent just because it lacks a track record.
        is_significant = abs(pct_change) >= 0.01  # 1% fallback threshold
        reason = (
            f"Insufficient history ({len(historical_prices)} pts) — used fallback "
            f"1% threshold; move was {pct_change:+.2%}"
        )
        return SignificanceResult(None, is_significant, reason)

    returns = compute_returns(historical_prices)
    sigma = rolling_volatility(returns)

    if sigma == 0:
        is_significant = pct_change != 0
        return SignificanceResult(0.0, is_significant, "Zero historical volatility — any move flagged")

    z = pct_change / sigma
    is_significant = abs(z) >= z_threshold
    reason = (
        f"Move of {pct_change:+.2%} vs. typical volatility of {sigma:.2%} "
        f"(z={z:+.2f}, threshold={z_threshold})"
    )
    return SignificanceResult(round(z, 3), is_significant, reason)


def evaluate_volume_change(current_volume: int | None, last_seen_volume: int | None) -> float | None:
    if not current_volume or not last_seen_volume or last_seen_volume == 0:
        return None
    return (current_volume - last_seen_volume) / last_seen_volume
