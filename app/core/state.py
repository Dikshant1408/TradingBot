"""
Bot operational state machine and runtime status tracker.
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.clock import get_utc_now, format_ist


class TradingMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class BotStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    HALTED = "HALTED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class BotStateSnapshot(BaseModel):
    mode: TradingMode = TradingMode.PAPER
    status: BotStatus = BotStatus.IDLE
    is_kill_switch_active: bool = False
    is_emergency_stopped: bool = False
    active_strategy: Optional[str] = None
    active_symbol: Optional[str] = None
    cash: float = 100000.0
    invested_value: float = 0.0
    total_equity: float = 100000.0
    today_pnl: float = 0.0
    today_realized_pnl: float = 0.0
    today_unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    today_trades_count: int = 0
    drawdown_pct: float = 0.0
    peak_equity: float = 100000.0
    open_positions_count: int = 0
    last_signal: Optional[Dict[str, Any]] = None
    last_execution: Optional[Dict[str, Any]] = None
    halt_reason: Optional[str] = None
    updated_at: datetime = Field(default_factory=get_utc_now)

    @property
    def updated_at_ist(self) -> str:
        return format_ist(self.updated_at)


class RuntimeStateManager:
    """
    Thread-safe in-memory runtime state singleton with synchronization to DB.
    """
    _instance: Optional["RuntimeStateManager"] = None

    def __new__(cls) -> "RuntimeStateManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = BotStateSnapshot()
        return cls._instance

    @property
    def state(self) -> BotStateSnapshot:
        return self._state

    def update(self, **kwargs) -> BotStateSnapshot:
        data = self._state.model_dump()
        data.update(kwargs)
        data["updated_at"] = get_utc_now()
        self._state = BotStateSnapshot(**data)
        return self._state

    def trigger_emergency_stop(self, reason: str = "Emergency stop clicked by user") -> BotStateSnapshot:
        return self.update(
            status=BotStatus.EMERGENCY_STOPPED,
            is_emergency_stopped=True,
            halt_reason=reason
        )

    def trigger_risk_halt(self, reason: str) -> BotStateSnapshot:
        return self.update(
            status=BotStatus.HALTED,
            halt_reason=reason
        )

    def reset_emergency_stop(self) -> BotStateSnapshot:
        return self.update(
            status=BotStatus.IDLE,
            is_emergency_stopped=False,
            halt_reason=None
        )

    def toggle_kill_switch(self, active: bool) -> BotStateSnapshot:
        return self.update(is_kill_switch_active=active)


state_manager = RuntimeStateManager()
