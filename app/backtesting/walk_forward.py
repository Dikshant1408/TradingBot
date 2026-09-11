"""
Rolling Walk-Forward Analysis Engine.
Validates strategy robustness across rolling in-sample (train) and out-of-sample (test) windows.
"""
from typing import List, Dict, Any, Type
import pandas as pd
from app.strategies.base import BaseStrategy
from app.backtesting.engine import BacktestEngine


class WalkForwardAnalyzer:
    """
    Executes rolling window walk-forward validation to detect parameter degradation.
    """

    @staticmethod
    def run_walk_forward(
        df: pd.DataFrame,
        symbol: str,
        strategy_class: Type[BaseStrategy],
        parameters: Dict[str, Any],
        train_bars: int = 100,
        test_bars: int = 40,
        initial_capital: float = 100000.0
    ) -> Dict[str, Any]:
        total_bars = len(df)
        window_size = train_bars + test_bars

        if total_bars < window_size:
            return {
                "error": f"Insufficient data for walk-forward. Total candles: {total_bars}, Required: {window_size}",
                "windows": []
            }

        windows = []
        step = test_bars
        current_start = 0

        while current_start + window_size <= total_bars:
            train_end = current_start + train_bars
            test_end = train_end + test_bars

            train_df = df.iloc[current_start:train_end].copy().reset_index(drop=True)
            test_df = df.iloc[train_end:test_end].copy().reset_index(drop=True)

            # In-sample run
            strat_in = strategy_class(parameters=parameters)
            engine_in = BacktestEngine(strategy=strat_in, initial_capital=initial_capital)
            res_in = engine_in.run(train_df, symbol)

            # Out-of-sample run
            strat_out = strategy_class(parameters=parameters)
            engine_out = BacktestEngine(strategy=strat_out, initial_capital=initial_capital)
            res_out = engine_out.run(test_df, symbol)

            windows.append({
                "window_index": len(windows) + 1,
                "in_sample_start": str(train_df["timestamp"].iloc[0])[:10],
                "in_sample_end": str(train_df["timestamp"].iloc[-1])[:10],
                "in_sample_return": res_in["metrics"]["return_pct"],
                "in_sample_win_rate": res_in["metrics"]["win_rate"],
                "out_sample_start": str(test_df["timestamp"].iloc[0])[:10],
                "out_sample_end": str(test_df["timestamp"].iloc[-1])[:10],
                "out_sample_return": res_out["metrics"]["return_pct"],
                "out_sample_win_rate": res_out["metrics"]["win_rate"],
            })

            current_start += step

        # Overall Walk-Forward Efficiency (Average Out-Sample Return / Average In-Sample Return)
        avg_in = sum(w["in_sample_return"] for w in windows) / len(windows) if windows else 0.0
        avg_out = sum(w["out_sample_return"] for w in windows) / len(windows) if windows else 0.0
        wfe = round((avg_out / avg_in) * 100, 1) if avg_in > 0 else 0.0

        return {
            "total_windows": len(windows),
            "avg_in_sample_return": round(avg_in, 2),
            "avg_out_sample_return": round(avg_out, 2),
            "walk_forward_efficiency_pct": wfe,
            "windows": windows
        }
