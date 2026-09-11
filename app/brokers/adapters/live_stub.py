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


class LiveBrokerPreflightChecker:
    """
    Performs comprehensive pre-flight verification before live execution.
    """

    @staticmethod
    def run_preflight() -> Dict[str, Any]:
        """
        Checklist for live trading readiness:
        1. Application mode is explicitly 'live'
        2. Broker credentials populated in environment
        3. Double confirmation accepted by user
        4. Kill switch is deactivated
        5. Emergency stop is inactive
        6. Risk limits configured (> 0)
        """
        results = {
            "mode_is_live": settings.APP_MODE == "live",
            "credentials_present": bool(settings.BROKER_API_KEY and settings.BROKER_API_SECRET),
            "double_confirmation_accepted": settings.LIVE_CONFIRMATION_ACCEPTED,
            "kill_switch_inactive": not state_manager.state.is_kill_switch_active,
            "emergency_stop_inactive": not state_manager.state.is_emergency_stopped,
            "risk_limits_configured": settings.MAX_DAILY_LOSS > 0 and settings.MAX_DRAWDOWN_PERCENT > 0,
            "all_passed": False
        }

        results["all_passed"] = all([
            results["mode_is_live"],
            results["credentials_present"],
            results["double_confirmation_accepted"],
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
