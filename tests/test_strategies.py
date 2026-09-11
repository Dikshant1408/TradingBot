import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from app.strategies.moving_average import MovingAverageCrossoverStrategy
from app.strategies.base import SignalAction


def test_strategy_parameter_validation():
    # Fast must be < Slow
    with pytest.raises(ValueError, match="strictly less than Slow MA"):
        MovingAverageCrossoverStrategy({"fast_period": 50, "slow_period": 20})

    # Fast must be > 0
    with pytest.raises(ValueError, match="must be > 0"):
        MovingAverageCrossoverStrategy({"fast_period": 0, "slow_period": 20})

    # Valid parameters should pass
    strat = MovingAverageCrossoverStrategy({"fast_period": 5, "slow_period": 10})
    assert strat.parameters["fast_period"] == 5
    assert strat.parameters["slow_period"] == 10


def test_moving_average_crossover_signals():
    strat = MovingAverageCrossoverStrategy({"fast_period": 3, "slow_period": 5, "direction": "LONG_ONLY"})

    # Price series designed to start with fast MA below slow MA, then cross up, then cross down
    prices = [100.0, 100.0, 100.0, 98.0, 95.0, 90.0, 110.0, 125.0, 115.0, 90.0, 80.0, 75.0]
    base_time = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)

    candles = []
    for i, p in enumerate(prices):
        candles.append({
            "timestamp": (base_time + timedelta(days=i)).isoformat(),
            "open": p - 1,
            "high": p + 2,
            "low": p - 2,
            "close": p,
            "volume": 1000,
            "symbol": "TEST_SYM"
        })

    df = pd.DataFrame(candles)

    all_signals = []
    for i in range(len(df)):
        candle = df.iloc[i]
        history = df.iloc[:i + 1]
        portfolio_state = {"positions": {"TEST_SYM": {"quantity": 10, "side": "LONG"}} if len(all_signals) > 0 else {}}
        sigs = strat.on_bar(candle, history, portfolio_state)
        all_signals.extend(sigs)

    actions = [s.action for s in all_signals]
    assert SignalAction.BUY in actions
    assert SignalAction.EXIT in actions
