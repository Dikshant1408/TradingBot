"""
Live Trading Safety Gate & Pre-Flight Check API.
Enforces strict gating and pre-flight validation before real broker access.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.brokers.adapters.live_stub import LiveBrokerPreflightChecker
from app.config.settings import get_settings, process_security_context
from app.core.audit import record_audit_log

router = APIRouter(prefix="/api/live", tags=["Live Trading Gate"])
settings = get_settings()


class LiveConfirmationRequest(BaseModel):
    statement_acknowledged: bool
    confirmation_phrase: str


@router.get("/preflight")
def check_live_preflight():
    """
    Run pre-flight validation checklist for live trading readiness.
    """
    results = LiveBrokerPreflightChecker.run_preflight()
    return {
        "checklist": results,
        "mode": settings.APP_MODE,
        "is_locked": not results["all_passed"],
        "hard_flag_enabled": settings.LIVE_TRADING_ENABLED,
        "process_authorized": process_security_context.is_authorized(),
        "broker": settings.BROKER_NAME or "None configured",
        "documentation_reference": "docs/broker-integration.md",
        "regulatory_notice": "Under SEBI regulations, automated trading APIs require broker approval and token renewal."
    }


@router.post("/confirm")
def confirm_live_trading(req: LiveConfirmationRequest):
    """
    Accept explicit manual authorization for the current process session only.
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

    success = process_security_context.authorize_session(req.confirmation_phrase)
    if not success:
        record_audit_log("USER", "LIVE_AUTH_FAILED", "live_gate", {"reason": "Phrase verification failed"})
        raise HTTPException(status_code=400, detail="Failed to authorize live session.")

    record_audit_log("USER", "LIVE_AUTH_GRANTED", "live_gate", {"broker": settings.BROKER_NAME})

    return {
        "status": "AUTHORIZED",
        "message": "Process session authorized. NOTE: Authorization will automatically expire when the application restarts."
    }


@router.post("/revoke")
def revoke_live_trading():
    """Immediately revoke in-memory live trading authorization."""
    process_security_context.revoke_session()
    record_audit_log("USER", "LIVE_AUTH_REVOKED", "live_gate", {})
    return {"status": "REVOKED", "message": "Live trading authorization revoked."}
