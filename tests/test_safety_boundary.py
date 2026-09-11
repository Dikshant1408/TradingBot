import pytest
from app.brokers.adapters.paper_adapter import PaperBroker
from app.brokers.adapters.live_stub import LiveBrokerStub, LiveBrokerPreflightChecker
from app.core.exceptions import LiveTradingBlockedError
from app.config.settings import get_settings

settings = get_settings()


def test_paper_broker_never_live():
    paper = PaperBroker()
    assert paper.is_live is False


def test_live_broker_strictly_blocked_by_default():
    live_broker = LiveBrokerStub()
    assert live_broker.is_live is True

    # Preflight check must fail in default configuration
    preflight = LiveBrokerPreflightChecker.run_preflight()
    assert preflight["all_passed"] is False

    # Attempting to place an order without meeting all 10 safety checks must raise LiveTradingBlockedError
    with pytest.raises(LiveTradingBlockedError):
        live_broker.place_order("NIFTY50", "BUY", 25, price=24000.0)

    # Attempting to fetch account without preflight passing must raise LiveTradingBlockedError
    with pytest.raises(LiveTradingBlockedError):
        live_broker.get_account()
