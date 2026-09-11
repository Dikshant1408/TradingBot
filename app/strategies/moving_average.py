"""
Moving Average Crossover Strategy (SMA/EMA).
Example configurable strategy for demonstration and verification.
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from app.strategies.base import BaseStrategy, Signal, SignalAction
from app.core.exceptions import TradingBotError


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy.
    Generates BUY signal when Fast MA crosses above Slow MA.
    Generates EXIT/SELL signal when Fast MA crosses below Slow MA.
    """
    name: str = "MA_Crossover"
    version: str = "1.0.0"
    description: str = "Dual Moving Average Crossover (Fast MA crosses Slow MA)"

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_period": 20,
            "slow_period": 50,
            "ma_type": "SMA",  # SMA or EMA
            "direction": "LONG_ONLY",  # LONG_ONLY, SHORT_ONLY, BOTH
            "stop_loss_pct": 0.02,  # 2% stop loss
            "take_profit_pct": 0.04,  # 4% profit target
        }
        if parameters:
            default_params.update(parameters)
        super().__init__(default_params)

    def validate_parameters(self) -> None:
        fast = int(self.parameters.get("fast_period", 20))
        slow = int(self.parameters.get("slow_period", 50))
        ma_type = str(self.parameters.get("ma_type", "SMA")).upper()
        direction = str(self.parameters.get("direction", "LONG_ONLY")).upper()

        if fast <= 0:
            raise ValueError(f"Fast MA period must be > 0. Got {fast}")
        if slow <= 0:
            raise ValueError(f"Slow MA period must be > 0. Got {slow}")
        if fast >= slow:
            raise ValueError(f"Fast MA ({fast}) must be strictly less than Slow MA ({slow})")
        if ma_type not in ["SMA", "EMA"]:
            raise ValueError(f"Invalid ma_type '{ma_type}'. Must be 'SMA' or 'EMA'")
        if direction not in ["LONG_ONLY", "SHORT_ONLY", "BOTH"]:
            raise ValueError(f"Invalid direction '{direction}'. Must be 'LONG_ONLY', 'SHORT_ONLY', or 'BOTH'")

        self.parameters["fast_period"] = fast
        self.parameters["slow_period"] = slow
        self.parameters["ma_type"] = ma_type
        self.parameters["direction"] = direction

    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "fast_period": {"type": "integer", "default": 20, "min": 2, "max": 200, "label": "Fast MA Period"},
            "slow_period": {"type": "integer", "default": 50, "min": 5, "max": 500, "label": "Slow MA Period"},
            "ma_type": {"type": "select", "options": ["SMA", "EMA"], "default": "SMA", "label": "MA Type"},
            "direction": {"type": "select", "options": ["LONG_ONLY", "SHORT_ONLY", "BOTH"], "default": "LONG_ONLY", "label": "Trading Direction"},
            "stop_loss_pct": {"type": "float", "default": 0.02, "min": 0.0, "max": 0.20, "label": "Stop Loss (%)"},
            "take_profit_pct": {"type": "float", "default": 0.04, "min": 0.0, "max": 0.50, "label": "Take Profit (%)"},
        }

    def on_bar(
        self,
        current_candle: pd.Series,
        historical_candles: pd.DataFrame,
        portfolio_state: Optional[Dict[str, Any]] = None
    ) -> List[Signal]:
        """
        Evaluate crossover using strictly available historical bars up to current_candle.
        Prevents lookahead bias.
        """
        fast_p = self.parameters["fast_period"]
        slow_p = self.parameters["slow_period"]
        ma_type = self.parameters["ma_type"]
        direction = self.parameters["direction"]
        sl_pct = self.parameters.get("stop_loss_pct", 0.02)
        tp_pct = self.parameters.get("take_profit_pct", 0.04)

        # We need at least slow_p + 1 candles to detect a crossover
        if len(historical_candles) < slow_p + 1:
            return []

        closes = historical_candles["close"]

        if ma_type == "SMA":
            fast_ma = closes.rolling(window=fast_p).mean()
            slow_ma = closes.rolling(window=slow_p).mean()
        else:  # EMA
            fast_ma = closes.ewm(span=fast_p, adjust=False).mean()
            slow_ma = closes.ewm(span=slow_p, adjust=False).mean()

        fast_curr = fast_ma.iloc[-1]
        slow_curr = slow_ma.iloc[-1]
        fast_prev = fast_ma.iloc[-2]
        slow_prev = slow_ma.iloc[-2]

        if pd.isna(fast_curr) or pd.isna(slow_curr) or pd.isna(fast_prev) or pd.isna(slow_prev):
            return []

        symbol = current_candle.get("symbol", "UNKNOWN")
        timestamp = pd.to_datetime(current_candle["timestamp"])
        price = float(current_candle["close"])
        signals: List[Signal] = []

        # Bullish Crossover: Fast crosses above Slow
        bullish_cross = (fast_prev <= slow_prev) and (fast_curr > slow_curr)

        # Bearish Crossover: Fast crosses below Slow
        bearish_cross = (fast_prev >= slow_prev) and (fast_curr < slow_curr)

        has_open_position = False
        position_side = None
        if portfolio_state and "positions" in portfolio_state:
            pos = portfolio_state["positions"].get(symbol)
            if pos and pos.get("quantity", 0) > 0:
                has_open_position = True
                position_side = pos.get("side", "LONG")

        if bullish_cross and (direction in ["LONG_ONLY", "BOTH"]):
            if not has_open_position or position_side != "LONG":
                signals.append(Signal(
                    action=SignalAction.BUY,
                    symbol=symbol,
                    timestamp=timestamp,
                    price=price,
                    stop_loss=round(price * (1 - sl_pct), 2) if sl_pct > 0 else None,
                    target=round(price * (1 + tp_pct), 2) if tp_pct > 0 else None,
                    confidence=1.0,
                    reason=f"Bullish crossover: Fast MA ({fast_curr:.2f}) crossed above Slow MA ({slow_curr:.2f})",
                    metadata={"fast_ma": round(fast_curr, 2), "slow_ma": round(slow_curr, 2)}
                ))

        elif bearish_cross:
            if has_open_position and position_side == "LONG":
                # Exit long position
                signals.append(Signal(
                    action=SignalAction.EXIT,
                    symbol=symbol,
                    timestamp=timestamp,
                    price=price,
                    confidence=1.0,
                    reason=f"Bearish crossover: Fast MA ({fast_curr:.2f}) crossed below Slow MA ({slow_curr:.2f})",
                    metadata={"fast_ma": round(fast_curr, 2), "slow_ma": round(slow_curr, 2)}
                ))
            elif direction in ["SHORT_ONLY", "BOTH"]:
                signals.append(Signal(
                    action=SignalAction.SELL,
                    symbol=symbol,
                    timestamp=timestamp,
                    price=price,
                    stop_loss=round(price * (1 + sl_pct), 2) if sl_pct > 0 else None,
                    target=round(price * (1 - tp_pct), 2) if tp_pct > 0 else None,
                    confidence=1.0,
                    reason=f"Bearish short signal: Fast MA ({fast_curr:.2f}) crossed below Slow MA ({slow_curr:.2f})",
                    metadata={"fast_ma": round(fast_curr, 2), "slow_ma": round(slow_curr, 2)}
                ))

        return signals
