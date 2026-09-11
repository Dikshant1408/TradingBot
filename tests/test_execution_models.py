import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from app.backtesting.engine import BacktestEngine
from app.backtesting.execution_models import ExecutionModel
from app.strategies.moving_average import MovingAverageCrossoverStrategy


def generate_crossover_df():
    """Generates synthetic bars with clear crossover and deliberate open/close spread."""
    prices = [100.0, 100.0, 100.0, 98.0, 95.0, 90.0, 110.0, 125.0, 115.0, 90.0, 80.0, 75.0]
    base_time = datetime(2024, 6, 1, 9, 15, tzinfo=timezone.utc)
    
    data = []
    for i, p in enumerate(prices):
        # Deliberate gap: Open differs from Close
        data.append({
            "timestamp": (base_time + timedelta(days=i)).isoformat(),
            "open": p - 3.0,
            "high": p + 5.0,
            "low": p - 5.0,
            "close": p,
            "volume": 10000,
            "symbol": "TEST_SYM"
        })
    return pd.DataFrame(data)


def test_next_open_vs_same_close_execution():
    df = generate_crossover_df()

    strat_next = MovingAverageCrossoverStrategy(parameters={"fast_period": 3, "slow_period": 5, "direction": "LONG_ONLY"})
    strat_same = MovingAverageCrossoverStrategy(parameters={"fast_period": 3, "slow_period": 5, "direction": "LONG_ONLY"})

    # 1. Run with NEXT_OPEN (Realistic, safe default)
    engine_next_open = BacktestEngine(
        strategy=strat_next,
        initial_capital=100000.0,
        execution_model=ExecutionModel.NEXT_OPEN
    )
    res_next_open = engine_next_open.run(df=df, symbol="TEST_SYM")

    # 2. Run with SAME_CLOSE (Instant fill, lookahead/execution bias)
    engine_same_close = BacktestEngine(
        strategy=strat_same,
        initial_capital=100000.0,
        execution_model=ExecutionModel.SAME_CLOSE
    )
    res_same_close = engine_same_close.run(df=df, symbol="TEST_SYM")

    assert len(res_next_open["trades"]) > 0
    assert len(res_same_close["trades"]) > 0

    first_next = res_next_open["trades"][0]
    first_same = res_same_close["trades"][0]

    # In SAME_CLOSE, entry price is at candle close
    # In NEXT_OPEN, entry price is at NEXT candle open, so they must differ!
    assert first_next["entry_price"] != first_same["entry_price"]
