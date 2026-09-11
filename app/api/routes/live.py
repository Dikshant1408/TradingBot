"""
Live Trading Safety Gate & Pre-Flight Check API.
Enforces strict gating and pre-flight validation before real broker access.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.brokers.adapters.live_stub import LiveBrokerPreflightChecker
from app.config.settings import get_settings

router = APIRouter(prefix="/api/live", tags=["Live Trading Gate"])
settings = get_settings()


class LiveConfirmationRequest(BaseModel):
    statement_acknowledged: bool
    final_confirmation: bool


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
        "broker": settings.BROKER_NAME or "None configured",
        "documentation_reference": "docs/broker-integration.md",
        "regulatory_notice": "Under SEBI regulations, automated trading APIs require broker approval and token renewal."
    }


@router.post("/confirm")
def confirm_live_trading(req: LiveConfirmationRequest):
    """
    Accept explicit manual double confirmation for live trading.
    """
    if not req.statement_acknowledged or not req.final_confirmation:
        raise HTTPException(
            status_code=400,
            detail="Dual explicit confirmations are mandatory to unlock live trading."
        )

    preflight = LiveBrokerPreflightChecker.run_preflight()
    if not preflight["credentials_present"]:
        raise HTTPException(
            status_code=400,
            detail="Live trading blocked: Broker credentials missing in .env. Review docs/broker-integration.md."
        )

    settings.LIVE_CONFIRMATION_ACCEPTED = True
    return {
        "status": "AUTHORIZED",
        "message": "Double confirmation accepted. Safety checklist evaluated."
    }
