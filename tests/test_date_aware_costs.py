from datetime import datetime, timezone
from app.backtesting.indian_costs import IndianCostCalculator, MarketSegment


def test_futures_stt_pre_and_post_oct_2024():
    calc = IndianCostCalculator()
    price = 1000.0
    qty = 100  # Turnover = ₹100,000

    # 1. Pre-Budget (Before Oct 1, 2024): Futures STT on sell was 0.0125%
    date_pre = datetime(2024, 8, 15, tzinfo=timezone.utc)
    costs_pre = calc.calculate(
        side="SELL",
        price=price,
        quantity=qty,
        segment=MarketSegment.FUTURES,
        trade_date=date_pre
    )
    # 100,000 * 0.000125 = ₹12.50
    assert costs_pre.stt == 12.50
    assert "PRE_OCT_2024" in costs_pre.cost_regime

    # 2. Post-Budget (After Oct 1, 2024): Futures STT on sell increased to 0.02%
    date_post = datetime(2024, 10, 15, tzinfo=timezone.utc)
    costs_post = calc.calculate(
        side="SELL",
        price=price,
        quantity=qty,
        segment=MarketSegment.FUTURES,
        trade_date=date_post
    )
    # 100,000 * 0.0002 = ₹20.00
    assert costs_post.stt == 20.00
    assert "POST_OCT_2024" in costs_post.cost_regime


def test_options_stt_pre_and_post_oct_2024():
    calc = IndianCostCalculator()
    premium = 100.0
    qty = 500  # Premium Turnover = ₹50,000

    # 1. Pre-Budget: Options STT on sell was 0.0625% of premium
    date_pre = datetime(2024, 5, 1, tzinfo=timezone.utc)
    costs_pre = calc.calculate(
        side="SELL",
        price=premium,
        quantity=qty,
        segment=MarketSegment.OPTIONS,
        trade_date=date_pre
    )
    # 50,000 * 0.000625 = ₹31.25
    assert costs_pre.stt == 31.25

    # 2. Post-Budget: Options STT on sell increased to 0.1% of premium
    date_post = datetime(2024, 11, 1, tzinfo=timezone.utc)
    costs_post = calc.calculate(
        side="SELL",
        price=premium,
        quantity=qty,
        segment=MarketSegment.OPTIONS,
        trade_date=date_post
    )
    # 50,000 * 0.0010 = ₹50.00
    assert costs_post.stt == 50.00


def test_equity_delivery_charges_both_sides():
    calc = IndianCostCalculator()
    price = 2000.0
    qty = 25  # Turnover = ₹50,000

    # For delivery, STT is 0.1% on BOTH BUY and SELL
    buy_costs = calc.calculate(side="BUY", price=price, quantity=qty, segment=MarketSegment.EQUITY_DELIVERY)
    sell_costs = calc.calculate(side="SELL", price=price, quantity=qty, segment=MarketSegment.EQUITY_DELIVERY)

    # 50,000 * 0.001 = ₹50.00
    assert buy_costs.stt == 50.00
    assert sell_costs.stt == 50.00
