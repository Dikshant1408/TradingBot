import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from app.strategies.moving_average import MovingAverageCrossoverStrategy
from app.backtesting.engine import BacktestEngine


def test_backtest_engine_execution():
    strat = MovingAverageCrossoverStrategy({"fast_period": 3, "slow_period": 6})
    initial_cap = 100000.0
    engine = BacktestEngine(strategy=strat, initial_capital=initial_cap)

    # Deterministic price series that creates a profitable cycle
    prices = [100, 101, 102, 103, 105, 110, 115, 118, 112, 108, 100]
    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    candles = []
    for i, p in enumerate(prices):
        candles.append({
            "timestamp": (base_time + timedelta(days=i)).isoformat(),
            "open": p,
            "high": p + 1,
            "low": p - 1,
            "close": p,
            "volume": 1000,
            "symbol": "TEST_SYM"
        })
    df = pd.DataFrame(candles)

    result = engine.run(df, "TEST_SYM")

    assert "id" in result
    assert "metrics" in result
    metrics = result["metrics"]
    assert metrics["initial_capital"] == initial_cap
    assert "return_pct" in metrics
    assert "max_drawdown" in metrics
    assert "total_trades" in metrics
    assert len(result["equity_curve"]) == len(df)
