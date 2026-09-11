"""
Risk Limits and Guardrail Configuration Models.
"""
from pydantic import BaseModel, Field


class RiskLimits(BaseModel):
    """
    Configurable risk parameters and execution thresholds.
    """
    max_daily_loss: float = Field(default=5000.0, ge=0.0, description="Max daily loss in INR before trading halts")
    max_drawdown_pct: float = Field(default=0.05, ge=0.0, le=1.0, description="Max portfolio drawdown (e.g. 0.05 = 5%)")
    max_trades_per_day: int = Field(default=5, ge=1, description="Max allowed completed trades per trading day")
    max_position_size_value: float = Field(default=50000.0, ge=0.0, description="Max position size in INR per instrument")
    max_open_positions: int = Field(default=3, ge=1, description="Max concurrent open positions allowed")
    duplicate_order_cooldown_seconds: int = Field(default=10, ge=1, description="Cooldown to prevent duplicate orders")
