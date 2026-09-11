"""
Risk Management & Safety Control API endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.risk.limits import RiskLimits
from app.risk.manager import risk_manager
from app.core.state import state_manager
from app.notifications.telegram import telegram_notifier
from app.core.audit import record_audit_log

router = APIRouter(prefix="/api/risk", tags=["Risk"])


class UpdateLimitsRequest(BaseModel):
    max_daily_loss: float
    max_drawdown_pct: float
    max_trades_per_day: int
    max_position_size_value: float
    max_open_positions: int


class KillSwitchRequest(BaseModel):
    active: bool


class EmergencyStopRequest(BaseModel):
    reason: str = "User activated Emergency Stop via terminal button"


@router.get("/limits")
def get_risk_status():
    """Fetch current risk limits and real-time utilization."""
    state = state_manager.state
    utilization = risk_manager.get_utilization_report(state)
    return {
        "limits": risk_manager.limits.model_dump(),
        "utilization": utilization,
        "is_kill_switch_active": state.is_kill_switch_active,
        "is_emergency_stopped": state.is_emergency_stopped,
        "halt_reason": state.halt_reason
    }


@router.post("/limits")
def update_risk_limits(req: UpdateLimitsRequest):
    """Update active risk guardrail limits."""
    risk_manager.limits.max_daily_loss = req.max_daily_loss
    risk_manager.limits.max_drawdown_pct = req.max_drawdown_pct
    risk_manager.limits.max_trades_per_day = req.max_trades_per_day
    risk_manager.limits.max_position_size_value = req.max_position_size_value
    risk_manager.limits.max_open_positions = req.max_open_positions

    record_audit_log(
        actor="USER",
        action="UPDATE_RISK_LIMITS",
        component="risk_api",
        details=req.model_dump()
    )

    return {
        "message": "Risk limits updated successfully",
        "limits": risk_manager.limits.model_dump()
    }


@router.post("/kill-switch")
def toggle_kill_switch(req: KillSwitchRequest):
    """Toggle persistent kill switch."""
    state_manager.toggle_kill_switch(req.active)
    action = "ACTIVATED" if req.active else "DEACTIVATED"
    record_audit_log(
        actor="USER",
        action=f"KILL_SWITCH_{action}",
        component="risk_api",
        details={"active": req.active}
    )
    return {
        "message": f"Kill switch has been {action}.",
        "is_kill_switch_active": state_manager.state.is_kill_switch_active
    }


@router.post("/emergency-stop")
def trigger_emergency_stop(req: EmergencyStopRequest):
    """
    Prominent Emergency Stop Control:
    Immediately halts execution, logs event, and sends alerts.
    """
    from app.paper.engine import paper_engine
    paper_engine.emergency_stop(req.reason)
    telegram_notifier.notify_emergency_stop(req.reason)
    record_audit_log(
        actor="USER",
        action="EMERGENCY_STOP_TRIGGERED",
        component="risk_api",
        details={"reason": req.reason}
    )

    return {
        "status": "EMERGENCY_STOPPED",
        "message": "Emergency stop successfully triggered. Trading halted.",
        "reason": req.reason
    }


@router.post("/emergency-reset")
def reset_emergency_stop():
    """Manual reset of Emergency Stop after user inspection."""
    from app.paper.engine import paper_engine
    paper_engine.reset_emergency_stop()
    record_audit_log(
        actor="USER",
        action="EMERGENCY_STOP_RESET",
        component="risk_api",
        details={"status": "IDLE"}
    )
    return {
        "status": "IDLE",
        "message": "Emergency stop reset. System is back in IDLE state."
    }
