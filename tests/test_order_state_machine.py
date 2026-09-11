import pytest
from app.core.order_state import (
    OrderStatus,
    OrderStateMachine,
    OrderStateContext,
    InvalidOrderStateTransitionError,
    OrderUnknownStateLockoutError
)


def test_valid_order_state_progression():
    state = OrderStateContext(order_id="ord-001")
    assert state.status == OrderStatus.CREATED

    # Move to SUBMITTED
    state.transition_to(OrderStatus.SUBMITTED, reason="Sent to broker")
    assert state.status == OrderStatus.SUBMITTED

    # Move to ACKNOWLEDGED
    state.transition_to(OrderStatus.ACKNOWLEDGED, reason="Broker assigned exchange order id")
    assert state.status == OrderStatus.ACKNOWLEDGED

    # Move to FILLED
    state.transition_to(OrderStatus.FILLED, reason="Executed at LTP")
    assert state.status == OrderStatus.FILLED
    assert state.is_terminal is True


def test_partial_fill_to_filled():
    state = OrderStateContext(order_id="ord-002")
    state.transition_to(OrderStatus.SUBMITTED)
    state.transition_to(OrderStatus.ACKNOWLEDGED)
    state.transition_to(OrderStatus.PARTIALLY_FILLED, reason="10 of 50 filled")
    assert state.status == OrderStatus.PARTIALLY_FILLED
    assert state.is_terminal is False

    # Terminal fill
    state.transition_to(OrderStatus.FILLED, reason="Remaining 40 filled")
    assert state.status == OrderStatus.FILLED
    assert state.is_terminal is True


def test_invalid_order_state_transition():
    state = OrderStateContext(order_id="ord-003")
    state.transition_to(OrderStatus.SUBMITTED)
    state.transition_to(OrderStatus.REJECTED, reason="Margin insufficient")
    assert state.status == OrderStatus.REJECTED
    assert state.is_terminal is True

    # Attempting to move a terminal REJECTED order to FILLED must fail
    with pytest.raises(InvalidOrderStateTransitionError):
        state.transition_to(OrderStatus.FILLED)


def test_unknown_state_lockout():
    state = OrderStateContext(order_id="ord-004")
    state.transition_to(OrderStatus.SUBMITTED)
    state.transition_to(OrderStatus.UNKNOWN, reason="Network timeout calling broker API")

    assert state.status == OrderStatus.UNKNOWN

    # Any normal order operation must be locked out while UNKNOWN
    with pytest.raises(OrderUnknownStateLockoutError):
        state.transition_to(OrderStatus.FILLED)

    # Must explicitly reconcile before resuming
    state.reconcile(OrderStatus.FILLED, reconciliation_notes="Reconciled via tradebook query")
    assert state.status == OrderStatus.FILLED
