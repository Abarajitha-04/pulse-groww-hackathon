from app.services.significance import evaluate_significance, rolling_volatility, compute_returns


def _flat_history(base_price: float, n: int) -> list[float]:
    """A quiet stock: tiny, consistent daily wobble."""
    prices = [base_price]
    wobble = [0.001, -0.001, 0.0015, -0.0005, 0.0008, -0.0012, 0.0003, -0.0007, 0.0009, -0.0004]
    for i in range(n - 1):
        prices.append(prices[-1] * (1 + wobble[i % len(wobble)]))
    return prices


def _volatile_history(base_price: float, n: int) -> list[float]:
    """A choppy stock: routinely swings several percent a day."""
    prices = [base_price]
    wobble = [0.04, -0.035, 0.05, -0.045, 0.03, -0.06, 0.055, -0.02, 0.045, -0.03]
    for i in range(n - 1):
        prices.append(prices[-1] * (1 + wobble[i % len(wobble)]))
    return prices


def test_first_time_view_is_always_significant():
    result = evaluate_significance([100, 101, 102], current_price=103, last_seen_price=None)
    assert result.is_significant is True
    assert "First time" in result.reason


def test_same_pct_move_flagged_on_quiet_stock_but_not_volatile_stock():
    """The core claim of the whole project: a fixed % threshold would treat
    these identically. The z-score model must not."""
    history_quiet = _flat_history(100, 20)
    history_volatile = _volatile_history(100, 20)

    last_seen = 100.0
    current = 102.0  # a flat +2% move in both cases

    quiet_result = evaluate_significance(history_quiet, current, last_seen, min_history_points=8)
    volatile_result = evaluate_significance(history_volatile, current, last_seen, min_history_points=8)

    assert quiet_result.is_significant is True, "a 2% move on a quiet stock should be flagged"
    assert volatile_result.is_significant is False, (
        "a 2% move on a stock that swings 4-6% daily should NOT be flagged"
    )
    assert abs(quiet_result.z_score) > abs(volatile_result.z_score)


def test_insufficient_history_uses_fallback_threshold():
    result = evaluate_significance([100, 101], current_price=102, last_seen_price=100, min_history_points=8)
    assert result.z_score is None
    assert "fallback" in result.reason.lower()
    assert result.is_significant is True  # 2% > 1% fallback threshold


def test_zero_volatility_flags_any_nonzero_move():
    flat = [100.0] * 10
    result = evaluate_significance(flat, current_price=100.5, last_seen_price=100.0, min_history_points=8)
    assert result.is_significant is True


def test_no_move_is_not_significant():
    history = _flat_history(100, 20)
    result = evaluate_significance(history, current_price=100.0, last_seen_price=100.0, min_history_points=8)
    assert result.is_significant is False


def test_rolling_volatility_and_returns_basic_math():
    prices = [100, 101, 99, 102]
    returns = compute_returns(prices)
    assert len(returns) == 3
    vol = rolling_volatility(returns)
    assert vol > 0
