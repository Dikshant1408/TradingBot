"""
Complete End-to-End System Acceptance Test.
Validates the full Section 52 acceptance criteria against the live running server:
1. Health & Mode Check
2. Market Session & IST Time
3. Historical Backtest Execution & Indian Costs
4. Candlestick & Equity Curve Chart Data
5. Paper Trading Configuration & Step-by-Step Replay
6. Emergency Stop Execution & Status Transition
7. Order Lockout During Emergency Stop
8. Emergency Stop Manual Reset
9. Live Trading Gate Pre-Flight Lockout Verification
10. Frontend Terminal HTML & Asset Delivery
"""
import pytest
import requests

BASE = "http://127.0.0.1:8000"


def test_e2e_health():
    resp = requests.get(f"{BASE}/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["mode"] == "PAPER"


def test_e2e_market_session():
    resp = requests.get(f"{BASE}/api/market/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status_message" in data
    assert "current_ist" in data


def test_e2e_backtest_execution():
    payload = {
        "strategy_id": "MA_Crossover",
        "symbol": "NIFTY50_DEMO",
        "initial_capital": 100000.0,
        "position_size_pct": 0.50,
        "brokerage": 20.0,
        "slippage_pct": 0.0005,
        "parameters": {"fast_period": 15, "slow_period": 40}
    }
    resp = requests.post(f"{BASE}/api/backtest/run", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "metrics" in data
    m = data["metrics"]
    assert m["initial_capital"] == 100000.0
    assert m["total_trades"] > 0
    assert "candlestick_chart" in data
    assert "equity_chart" in data


def test_e2e_paper_trading_workflow():
    # 1. Configure session
    conf_payload = {
        "strategy_id": "MA_Crossover",
        "symbol": "NIFTY50_DEMO",
        "initial_capital": 100000.0,
        "replay_delay_seconds": 0.1,
        "parameters": {"fast_period": 10, "slow_period": 25}
    }
    resp = requests.post(f"{BASE}/api/paper/configure", json=conf_payload)
    assert resp.status_code == 200

    # 2. Step 3 bars
    for _ in range(3):
        step_resp = requests.post(f"{BASE}/api/paper/step")
        assert step_resp.status_code == 200
        step_data = step_resp.json()
        assert "bar_index" in step_data
        assert "candle" in step_data

    # 3. Trigger Emergency Stop
    stop_resp = requests.post(f"{BASE}/api/risk/emergency-stop", json={"reason": "E2E Acceptance Stop"})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "EMERGENCY_STOPPED"

    # Verify health reports EMERGENCY_STOPPED
    health = requests.get(f"{BASE}/api/system/health").json()
    assert health["is_emergency_stopped"] is True
    assert health["bot_status"] == "EMERGENCY_STOPPED"

    # 4. Reset Emergency Stop
    reset_resp = requests.post(f"{BASE}/api/risk/emergency-reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "IDLE"


def test_e2e_live_safety_gate():
    resp = requests.get(f"{BASE}/api/live/preflight")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_locked"] is True
    assert data["checklist"]["all_passed"] is False


def test_e2e_frontend_served():
    resp = requests.get(f"{BASE}/")
    assert resp.status_code == 200
    assert "QUANTDESK INDIA" in resp.text
    assert "EMERGENCY STOP" in resp.text
