import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config.settings import get_settings, process_security_context
from app.brokers.adapters.live_stub import LiveBrokerPreflightChecker, LiveBrokerStub
from app.core.exceptions import LiveTradingBlockedError

settings = get_settings()
client = TestClient(app)


def test_live_trading_hard_flag_default_false():
    """Live trading hard flag must be FALSE by default."""
    assert settings.LIVE_TRADING_ENABLED is False


def test_process_security_context_lifecycle():
    """Process authorization must be ephemeral, strict, and revokable."""
    # Ensure starting in revoked state
    process_security_context.revoke_session()
    assert process_security_context.is_authorized() is False

    # Bad phrase must fail
    res = process_security_context.authorize_session("i confirm live trading")
    assert res is False
    assert process_security_context.is_authorized() is False

    # Exact required phrase succeeds
    res = process_security_context.authorize_session("I CONFIRM LIVE TRADING AT MY OWN RISK")
    assert res is True
    assert process_security_context.is_authorized() is True

    # Revocation clears state immediately
    process_security_context.revoke_session()
    assert process_security_context.is_authorized() is False


def test_live_confirm_api_blocked_when_flag_false():
    """API endpoint /api/live/confirm must reject with 403 when LIVE_TRADING_ENABLED is False."""
    response = client.post("/api/live/confirm", json={
        "statement_acknowledged": True,
        "confirmation_phrase": "I CONFIRM LIVE TRADING AT MY OWN RISK"
    })
    assert response.status_code == 403
    assert "LIVE_TRADING_ENABLED" in response.json()["detail"]


def test_preflight_checks_fail_safely():
    """Live preflight checker must fail safely by default."""
    preflight = LiveBrokerPreflightChecker.run_preflight()
    assert preflight["all_passed"] is False
    assert preflight["hard_flag_enabled"] is False
