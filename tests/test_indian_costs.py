from app.backtesting.indian_costs import IndianCostCalculator


def test_indian_cost_calculator_buy():
    calc = IndianCostCalculator()
    price = 1000.0
    qty = 50  # Turnover = ₹50,000

    costs = calc.calculate(side="BUY", price=price, quantity=qty)

    # For BUY:
    # Brokerage: min(20, 50000 * 0.0003) = min(20, 15) = ₹15.0
    # STT: ₹0.0 for intraday buy
    # Exchange Charges: 50000 * 0.0000297 = ₹1.485 -> ₹1.49
    # Stamp Duty: 50000 * 0.00003 = ₹1.50
    # GST: 18% of (Brokerage + Exchange + SEBI)
    assert costs.brokerage == 15.0
    assert costs.stt == 0.0  # STT is 0 on BUY for intraday
    assert costs.stamp_duty == 1.50
    assert costs.total_costs > 0


def test_indian_cost_calculator_sell():
    calc = IndianCostCalculator()
    price = 1000.0
    qty = 50  # Turnover = ₹50,000

    costs = calc.calculate(side="SELL", price=price, quantity=qty)

    # For SELL:
    # STT: 50000 * 0.00025 = ₹12.50
    # Stamp Duty: ₹0.0 on SELL
    assert costs.stt == 12.50
    assert costs.stamp_duty == 0.0
    assert costs.total_costs > costs.stt
