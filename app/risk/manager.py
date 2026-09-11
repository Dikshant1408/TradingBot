"""
Comprehensive Risk Management Engine.
Enforces multi-layer safety checks: loss limits, drawdown limits, trade frequency limits,
duplicate order protection, emergency stop, and persistent kill switch.
"""
import time
import logging
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timezone
from app.risk.limits import RiskLimits
from app.core.state import BotStateSnapshot, state_manager, BotStatus
from app.core.exceptions import (
    RiskViolationError,
    EmergencyStopActiveError,
    KillSwitchActiveError,
    DuplicateOrderError
)
from app.core.event_bus import event_bus, EventType

logger = logging.getLogger("trading_bot.risk.manager")


class RiskManager:
    """
    Evaluates every trading intent against configured mathematical risk limits.
    Prevents account blow-up and accidental over-trading.
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self._recent_orders: List[Dict[str, Any]] = []

    def evaluate_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        current_state: BotStateSnapshot
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-trade risk gatekeeper. Returns (is_allowed, rejection_reason).
        """
        # 1. Emergency Stop Check
        if current_state.is_emergency_stopped or current_state.status == BotStatus.EMERGENCY_STOPPED:
            msg = "Execution BLOCKED: EMERGENCY STOP is active. Manual reset required."
            logger.critical(msg)
            return False, msg

        # 2. Persistent Kill Switch Check
        if current_state.is_kill_switch_active:
            msg = "Execution BLOCKED: KILL SWITCH is ON in database/settings."
            logger.critical(msg)
            return False, msg

        # 3. Bot Operational Status Check
        if current_state.status == BotStatus.HALTED:
            msg = f"Execution BLOCKED: Bot is HALTED ({current_state.halt_reason})."
            logger.warning(msg)
            return False, msg

        # 4. Maximum Daily Loss Limit
        if current_state.today_pnl <= -self.limits.max_daily_loss:
            msg = f"TRADING HALTED: Maximum daily loss of ₹{self.limits.max_daily_loss:.2f} reached (Current P&L: ₹{current_state.today_pnl:.2f})"
            logger.critical(msg)
            state_manager.trigger_risk_halt(msg)
            event_bus.emit(EventType.RISK_ALERT, {"reason": msg, "type": "MAX_DAILY_LOSS"})
            return False, msg

        # 5. Maximum Drawdown Limit
        if current_state.drawdown_pct >= self.limits.max_drawdown_pct:
            msg = f"TRADING HALTED: Max drawdown threshold of {self.limits.max_drawdown_pct * 100:.1f}% breached (Current: {current_state.drawdown_pct * 100:.1f}%)"
            logger.critical(msg)
            state_manager.trigger_risk_halt(msg)
            event_bus.emit(EventType.RISK_ALERT, {"reason": msg, "type": "MAX_DRAWDOWN"})
            return False, msg

        # 6. Maximum Daily Trades Count (Only limits new position opening)
        if side.upper() == "BUY" and current_state.today_trades_count >= self.limits.max_trades_per_day:
            msg = f"TRADING HALTED: Max trades limit of {self.limits.max_trades_per_day} trades/day reached."
            logger.warning(msg)
            state_manager.trigger_risk_halt(msg)
            event_bus.emit(EventType.RISK_ALERT, {"reason": msg, "type": "MAX_TRADES"})
            return False, msg

        # 7. Maximum Position Value Limit
        position_value = quantity * price
        if position_value > self.limits.max_position_size_value:
            msg = f"Order REJECTED: Order value ₹{position_value:.2f} exceeds max position size ₹{self.limits.max_position_size_value:.2f}"
            logger.warning(msg)
            return False, msg

        # 8. Maximum Open Positions Count
        if side.upper() == "BUY" and current_state.open_positions_count >= self.limits.max_open_positions:
            msg = f"Order REJECTED: Max open positions limit ({self.limits.max_open_positions}) reached."
            logger.warning(msg)
            return False, msg

        # 9. Duplicate Order Protection (cooldown window)
        now_ts = time.time()
        cooldown = self.limits.duplicate_order_cooldown_seconds
        for ro in self._recent_orders:
            if (
                ro["symbol"] == symbol and
                ro["side"] == side.upper() and
                ro["quantity"] == quantity and
                (now_ts - ro["timestamp"]) < cooldown
            ):
                msg = f"Order SUPPRESSED: Duplicate order detected within {cooldown}s cooldown window."
                logger.warning(msg)
                return False, msg

        # Record this order intent in recent orders queue
        self._recent_orders.append({
            "symbol": symbol,
            "side": side.upper(),
            "quantity": quantity,
            "price": price,
            "timestamp": now_ts
        })
        # Prune older than 60s
        self._recent_orders = [o for o in self._recent_orders if (now_ts - o["timestamp"]) < 60]

        return True, None

    def get_utilization_report(self, state: BotStateSnapshot) -> Dict[str, Any]:
        """
        Calculates current risk utilization metrics for the UI terminal dashboard.
        """
        daily_loss_utilization = (
            abs(min(0.0, state.today_pnl)) / self.limits.max_daily_loss
            if self.limits.max_daily_loss > 0 else 0.0
        )
        drawdown_utilization = (
            state.drawdown_pct / self.limits.max_drawdown_pct
            if self.limits.max_drawdown_pct > 0 else 0.0
        )
        trades_utilization = (
            state.today_trades_count / self.limits.max_trades_per_day
            if self.limits.max_trades_per_day > 0 else 0.0
        )

        return {
            "daily_loss": {
                "current": round(abs(min(0.0, state.today_pnl)), 2),
                "limit": self.limits.max_daily_loss,
                "pct": round(min(1.0, daily_loss_utilization) * 100, 1),
                "is_breached": state.today_pnl <= -self.limits.max_daily_loss
            },
            "drawdown": {
                "current": round(state.drawdown_pct * 100, 2),
                "limit": round(self.limits.max_drawdown_pct * 100, 2),
                "pct": round(min(1.0, drawdown_utilization) * 100, 1),
                "is_breached": state.drawdown_pct >= self.limits.max_drawdown_pct
            },
            "trades_count": {
                "current": state.today_trades_count,
                "limit": self.limits.max_trades_per_day,
                "pct": round(min(1.0, trades_utilization) * 100, 1),
                "is_breached": state.today_trades_count >= self.limits.max_trades_per_day
            },
            "open_positions": {
                "current": state.open_positions_count,
                "limit": self.limits.max_open_positions
            },
            "kill_switch": state.is_kill_switch_active,
            "emergency_stopped": state.is_emergency_stopped
        }


# Global RiskManager singleton
risk_manager = RiskManager()
