import pytest
from app.risk.manager import RiskManager
from app.risk.limits import RiskLimits
from app.core.state import BotStateSnapshot, BotStatus


def test_risk_manager_daily_loss_limit():
    limits = RiskLimits(max_daily_loss=5000.0)
    rm = RiskManager(limits)

    # State where today's PnL is negative beyond limit
    breached_state = BotStateSnapshot(today_pnl=-5500.0)
    allowed, reason = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, breached_state)
    assert not allowed
    assert "Maximum daily loss" in reason


def test_risk_manager_max_drawdown_limit():
    limits = RiskLimits(max_drawdown_pct=0.05)
    rm = RiskManager(limits)

    # Drawdown is 6% (> 5% limit)
    breached_state = BotStateSnapshot(drawdown_pct=0.06)
    allowed, reason = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, breached_state)
    assert not allowed
    assert "Max drawdown" in reason


def test_risk_manager_max_trades_limit():
    limits = RiskLimits(max_trades_per_day=3)
    rm = RiskManager(limits)

    breached_state = BotStateSnapshot(today_trades_count=3)
    allowed, reason = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, breached_state)
    assert not allowed
    assert "Max trades limit" in reason


def test_risk_manager_emergency_stop():
    rm = RiskManager()
    stopped_state = BotStateSnapshot(is_emergency_stopped=True, status=BotStatus.EMERGENCY_STOPPED)
    allowed, reason = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, stopped_state)
    assert not allowed
    assert "EMERGENCY STOP is active" in reason


def test_risk_manager_kill_switch():
    rm = RiskManager()
    kill_state = BotStateSnapshot(is_kill_switch_active=True)
    allowed, reason = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, kill_state)
    assert not allowed
    assert "KILL SWITCH is ON" in reason


def test_risk_manager_duplicate_order_protection():
    limits = RiskLimits(duplicate_order_cooldown_seconds=10)
    rm = RiskManager(limits)
    normal_state = BotStateSnapshot()

    # First order should succeed
    allowed1, _ = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, normal_state)
    assert allowed1

    # Immediate identical second order should be suppressed
    allowed2, reason2 = rm.evaluate_order("RELIANCE", "BUY", 10, 2500.0, normal_state)
    assert not allowed2
    assert "Duplicate order detected" in reason2
