from app.brokers.adapters.paper_adapter import PaperBroker


def test_paper_broker_virtual_execution():
    broker = PaperBroker(initial_capital=100000.0)
    assert broker.is_live is False
    assert broker.cash == 100000.0

    # Execute simulated BUY
    order = broker.place_order(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        price=2500.0,
        reason="Test buy"
    )
    assert order["status"] == "FILLED"
    assert broker.cash < 100000.0  # Debited purchase + Indian statutory costs
    assert "RELIANCE" in broker.positions
    pos = broker.positions["RELIANCE"]
    assert pos["quantity"] == 10

    # Update market price and check unrealized P&L
    broker.update_market_price("RELIANCE", 2600.0)
    acc = broker.get_account()
    assert acc["unrealized_pnl"] > 0

    # Execute simulated SELL / EXIT
    exit_order = broker.place_order(
        symbol="RELIANCE",
        side="SELL",
        quantity=10,
        price=2600.0,
        reason="Test exit"
    )
    assert exit_order["status"] == "FILLED"
    assert "RELIANCE" not in broker.positions
    assert len(broker.trades) == 1
    trade = broker.trades[0]
    assert trade["net_pnl"] > 0
