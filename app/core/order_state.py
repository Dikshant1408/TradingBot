"""
Formal Order State Machine and Reconciliation Safety Guard.
Enforces valid state lifecycles and provides an emergency lock on UNKNOWN order status.
"""
from enum import Enum
from typing import Set, Dict, Optional
import logging
from app.core.exceptions import TradingBotError

logger = logging.getLogger("trading_bot.core.order_state")


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"  # Safety critical state: requires immediate reconciliation!


class OrderIntent(str, Enum):
    """
    Explicit order intent to prevent semantic confusion between SELL and EXIT.
    Prevents unintentional short sales or accidental flat position closures.
    """
    BUY_TO_OPEN = "BUY_TO_OPEN"       # Open or augment a LONG position
    SELL_TO_CLOSE = "SELL_TO_CLOSE"   # Liquidate or reduce a LONG position
    SELL_TO_OPEN = "SELL_TO_OPEN"     # Initiate or augment a SHORT position
    BUY_TO_CLOSE = "BUY_TO_CLOSE"     # Cover or reduce a SHORT position


# Valid state transitions
VALID_TRANSITIONS: Dict[OrderStatus, Set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.SUBMITTED: {OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED, OrderStatus.FILLED, OrderStatus.UNKNOWN},
    OrderStatus.ACKNOWLEDGED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED, OrderStatus.UNKNOWN},
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.UNKNOWN},
    OrderStatus.FILLED: set(),      # Terminal state
    OrderStatus.CANCELLED: set(),   # Terminal state
    OrderStatus.REJECTED: set(),    # Terminal state
    OrderStatus.EXPIRED: set(),     # Terminal state
    OrderStatus.UNKNOWN: {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}  # Only reconciled states
}


class InvalidOrderStateTransitionError(TradingBotError):
    """Raised when an illegal order state transition is attempted."""
    pass


class UnknownOrderStateLockError(TradingBotError):
    """Raised when order operations are attempted while an order status is UNKNOWN."""
    pass


OrderUnknownStateLockoutError = UnknownOrderStateLockError


class OrderStateMachine:
    """
    Validates lifecycle transitions for orders.
    Enforces strict reconciliation when broker state is uncertain.
    """

    @staticmethod
    def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
        if current == target:
            return True
        allowed = VALID_TRANSITIONS.get(current, set())
        return target in allowed

    @classmethod
    def transition(cls, order_id: str, current: OrderStatus, target: OrderStatus) -> OrderStatus:
        if not cls.can_transition(current, target):
            msg = f"Invalid order state transition for {order_id}: {current.value} -> {target.value}"
            logger.error(msg)
            raise InvalidOrderStateTransitionError(msg)

        if target == OrderStatus.UNKNOWN:
            msg = (
                f"🚨 CRITICAL SAFETY EVENT: Order {order_id} has entered UNKNOWN status! "
                "Halting new order submissions until state is reconciled."
            )
            logger.critical(msg)

        logger.info(f"Order {order_id} transitioned: {current.value} -> {target.value}")
        return target


class OrderStateContext:
    """
    Stateful wrapper for managing an individual order's transitions and enforcing lockout.
    """

    def __init__(self, order_id: str, initial_status: OrderStatus = OrderStatus.CREATED):
        self.order_id = order_id
        self.status = initial_status
        self.is_reconciled = False

    @property
    def is_terminal(self) -> bool:
        return self.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}

    def transition_to(self, target: OrderStatus, reason: Optional[str] = None) -> OrderStatus:
        if self.status == OrderStatus.UNKNOWN:
            raise OrderUnknownStateLockoutError(
                f"Order {self.order_id} is in UNKNOWN status. All normal order operations are locked out."
            )
        self.status = OrderStateMachine.transition(self.order_id, self.status, target)
        return self.status

    def reconcile(self, target: OrderStatus, reconciliation_notes: str = "") -> OrderStatus:
        if target not in VALID_TRANSITIONS[OrderStatus.UNKNOWN]:
            raise InvalidOrderStateTransitionError(
                f"Cannot reconcile UNKNOWN order into {target.value}."
            )
        logger.warning(f"Reconciled order {self.order_id} from UNKNOWN -> {target.value}: {reconciliation_notes}")
        self.status = target
        self.is_reconciled = True
        return self.status
