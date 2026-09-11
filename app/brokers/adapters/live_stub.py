"""
Live Broker Adapter (Safety Stub & Pre-flight Gatekeeper).
Enforces Section 30, 31, and 54 regulatory and safety gates.
Strictly BLOCKED until explicitly verified, authenticated, and authorized.
"""
import logging
from typing import Dict, List, Optional, Any
from app.brokers.base import BaseBroker
from app.core.exceptions import LiveTradingBlockedError, KillSwitchActiveError
from app.config.settings import get_settings
from app.core.state import state_manager

logger = logging.getLogger("trading_bot.brokers.live_stub")
settings = get_settings()


from app.config.settings import get_settings, process_security_context


class LiveBrokerPreflightChecker:
    """
    Performs comprehensive pre-flight verification before live execution.
    """

    @staticmethod
    def run_preflight() -> Dict[str, Any]:
        """
        Checklist for live trading readiness:
        1. Application mode is explicitly 'live'
        2. Independent hard flag LIVE_TRADING_ENABLED is True
        3. Ephemeral process-lifetime session is authorized
        4. Broker credentials populated in environment
        5. Kill switch is deactivated
        6. Emergency stop is inactive
        7. Risk limits configured (> 0)
        """
        results = {
            "mode_is_live": settings.APP_MODE == "live",
            "hard_flag_enabled": settings.LIVE_TRADING_ENABLED is True,
            "process_session_authorized": process_security_context.is_authorized(),
            "credentials_present": bool(settings.BROKER_API_KEY and settings.BROKER_API_SECRET),
            "kill_switch_inactive": not state_manager.state.is_kill_switch_active,
            "emergency_stop_inactive": not state_manager.state.is_emergency_stopped,
            "risk_limits_configured": settings.MAX_DAILY_LOSS > 0 and settings.MAX_DRAWDOWN_PERCENT > 0,
            "all_passed": False
        }

        results["all_passed"] = all([
            results["mode_is_live"],
            results["hard_flag_enabled"],
            results["process_session_authorized"],
            results["credentials_present"],
            results["kill_switch_inactive"],
            results["emergency_stop_inactive"],
            results["risk_limits_configured"]
        ])
        return results


class LiveBrokerStub(BaseBroker):
    """
    Live broker adapter that strictly guards real exchange execution.
    Raises LiveTradingBlockedError if preflight conditions fail.
    """

    def __init__(self):
        self._is_live = True

    @property
    def is_live(self) -> bool:
        return True

    def _verify_execution_allowed(self) -> None:
        preflight = LiveBrokerPreflightChecker.run_preflight()
        if not preflight["all_passed"]:
            failed = [k for k, v in preflight.items() if not v and k != "all_passed"]
            logger.critical(f"LIVE EXECUTION REJECTED! Failed preflight checks: {failed}")
            raise LiveTradingBlockedError(
                f"Live trading blocked: Failed safety checks: {', '.join(failed)}. "
                "See docs/broker-integration.md for broker authorization instructions."
            )

    def get_account(self) -> Dict[str, Any]:
        self._verify_execution_allowed()
        return {
            "mode": "LIVE",
            "status": "CONNECTED",
            "broker": settings.BROKER_NAME or "UNCONFIGURED"
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        self._verify_execution_allowed()
        return []

    def get_orders(self) -> List[Dict[str, Any]]:
        self._verify_execution_allowed()
        return []

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        self._verify_execution_allowed()
        return None

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        reason: str = ""
    ) -> Dict[str, Any]:
        self._verify_execution_allowed()
        raise LiveTradingBlockedError(
            "Live order submission requires completed broker integration. "
            "Refer to Section 54 review before connecting live capital."
        )

    def cancel_order(self, order_id: str) -> bool:
        self._verify_execution_allowed()
        return False
