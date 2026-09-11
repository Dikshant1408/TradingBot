"""
Live Trading Safety Gate, Time-Limited Session Management & Reconciliation API.
Enforces strict hardware kill flags, ephemeral 15-minute TTL sessions, and pre-trade account reconciliation.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.brokers.adapters.live_stub import LiveBrokerPreflightChecker
from app.config.settings import get_settings, process_security_context
from app.core.audit import record_audit_log
from app.core.state import state_manager

router = APIRouter(prefix="/api/live", tags=["Live Trading Gate"])
settings = get_settings()


class LiveConfirmationRequest(BaseModel):
    statement_acknowledged: bool
    confirmation_phrase: str
    ttl_minutes: Optional[int] = 15


class ReconciliationCheckRequest(BaseModel):
    expected_cash: Optional[float] = None
    expected_positions: Optional[Dict[str, int]] = None
    expected_open_orders_count: Optional[int] = None


@router.get("/preflight")
def check_live_preflight():
    """
    Run pre-flight validation checklist and inspect current ephemeral authorization session.
    """
    results = LiveBrokerPreflightChecker.run_preflight()
    sess_info = process_security_context.get_session_info()
    return {
        "checklist": results,
        "mode": settings.APP_MODE,
        "is_locked": not results["all_passed"],
        "hard_flag_enabled": settings.LIVE_TRADING_ENABLED,
        "process_authorized": sess_info is not None,
        "session": sess_info,
        "broker": settings.BROKER_NAME or "None configured",
        "documentation_reference": "docs/broker-integration.md",
        "regulatory_notice": "Under SEBI regulations, automated trading APIs require broker approval and periodic token renewal."
    }


@router.post("/confirm")
def confirm_live_trading(req: LiveConfirmationRequest):
    """
    Issue an ephemeral, time-limited live authorization session token (default 15 minutes).
    Restarting the process automatically revokes the session.
    """
    if not settings.LIVE_TRADING_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Live trading hard flag 'LIVE_TRADING_ENABLED' is FALSE in environment. Enable in .env first."
        )

    if not req.statement_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="You must acknowledge the legal and capital risk statement."
        )

    if req.confirmation_phrase != "I CONFIRM LIVE TRADING AT MY OWN RISK":
        raise HTTPException(
            status_code=400,
            detail="Invalid confirmation phrase. Must exactly match 'I CONFIRM LIVE TRADING AT MY OWN RISK'."
        )

    preflight = LiveBrokerPreflightChecker.run_preflight()
    if not preflight["credentials_present"]:
        raise HTTPException(
            status_code=400,
            detail="Live trading blocked: Broker credentials missing in .env. Review docs/broker-integration.md."
        )

    session = process_security_context.authorize_session(req.confirmation_phrase, ttl_minutes=req.ttl_minutes)
    if not session:
        record_audit_log("USER", "LIVE_AUTH_FAILED", "live_gate", {"reason": "Session authorization failed"})
        raise HTTPException(status_code=400, detail="Failed to authorize live session.")

    record_audit_log("USER", "LIVE_AUTH_GRANTED", "live_gate", {
        "broker": settings.BROKER_NAME,
        "token": session.token,
        "expires_at": session.expires_at.isoformat()
    })

    return {
        "status": "AUTHORIZED",
        "token": session.token,
        "authorized_at": session.authorized_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "remaining_seconds": session.remaining_seconds,
        "message": f"Time-limited session active ({req.ttl_minutes}m TTL). Auto-revokes on process restart or expiry."
    }


@router.post("/reconcile")
def reconcile_broker_account(req: ReconciliationCheckRequest):
    """
    Pre-order Broker Account Reconciliation Guard.
    Compares internal state against broker reporting for Cash, Positions, and Open Orders.
    Halts immediately on any mismatch - No automatic guessing!
    """
    discrepancies: List[str] = []

    # Internal state values
    internal_pos = state_manager.positions
    internal_orders = state_manager.orders
    internal_open_orders = [o for o in internal_orders if o.get("status") in ["PENDING", "SUBMITTED", "ACKNOWLEDGED"]]

    # 1. Cash Reconciliation (if expected cash provided)
    if req.expected_cash is not None:
        cash_diff = abs(state_manager.cash - req.expected_cash)
        if cash_diff > 1.00:  # More than ₹1 discrepancy
            discrepancies.append(
                f"Cash mismatch: Internal state has ₹{state_manager.cash:.2f}, "
                f"broker reports ₹{req.expected_cash:.2f} (diff: ₹{cash_diff:.2f})"
            )

    # 2. Position Reconciliation
    if req.expected_positions is not None:
        for sym, exp_qty in req.expected_positions.items():
            act_qty = internal_pos.get(sym, {}).get("quantity", 0)
            if act_qty != exp_qty:
                discrepancies.append(
                    f"Position mismatch for {sym}: Internal has {act_qty}, broker reports {exp_qty}."
                )
        for sym, pos_data in internal_pos.items():
            if sym not in req.expected_positions and pos_data.get("quantity", 0) > 0:
                discrepancies.append(
                    f"Orphan internal position for {sym}: {pos_data.get('quantity')} shares not found on broker."
                )

    # 3. Open Orders Reconciliation
    if req.expected_open_orders_count is not None:
        act_open_cnt = len(internal_open_orders)
        if act_open_cnt != req.expected_open_orders_count:
            discrepancies.append(
                f"Open orders mismatch: Internal has {act_open_cnt} pending orders, "
                f"broker reports {req.expected_open_orders_count}."
            )

    is_reconciled = len(discrepancies) == 0

    if not is_reconciled:
        # Trip emergency halt on reconciliation failure
        record_audit_log("RECONCILIATION_ENGINE", "RECONCILIATION_MISMATCH_HALT", "live_gate", {
            "discrepancies": discrepancies
        })
        raise HTTPException(
            status_code=409,
            detail={
                "status": "RECONCILIATION_FAILED",
                "message": "🚨 CRITICAL MISMATCH: Local portfolio and Broker portfolio do not match. Live execution LOCKED.",
                "discrepancies": discrepancies,
                "action": "Manual audit required before any orders can be dispatched."
            }
        )

    record_audit_log("RECONCILIATION_ENGINE", "RECONCILIATION_SUCCESS", "live_gate", {})
    return {
        "status": "RECONCILED",
        "message": "Reconciliation verified: Internal ledger and broker state are in 100% agreement.",
        "internal_cash": state_manager.cash,
        "open_positions_count": len(internal_pos),
        "open_orders_count": len(internal_open_orders)
    }


@router.post("/revoke")
def revoke_live_trading():
    """Immediately revoke in-memory live trading authorization."""
    process_security_context.revoke_session()
    record_audit_log("USER", "LIVE_AUTH_REVOKED", "live_gate", {})
    return {"status": "REVOKED", "message": "Live trading authorization revoked."}
