# Backtesting Engine & Indian Regulatory Cost Modeling

QuantDesk India features a chronological, event-driven backtesting engine with realistic Indian equity and derivative statutory cost simulations.

## Zero Lookahead Bias Guarantee
1. **Chronological Candle Loop**: Bars are processed strictly from oldest to newest.
2. **Historical Window Slicing**: When candle at time $t$ is evaluated, the strategy's `on_bar()` method only receives data up to and including bar $t$.
3. **Execution Modeling**: Orders generated at bar $t$ are filled at the close of bar $t$ or open of bar $t+1$ with market impact slippage applied.

## Indian Statutory Transaction Cost Breakdown

Every executed order incurs realistic Indian exchange and government statutory charges:

1. **Brokerage**: Flat ₹20 per executed order or percentage.
2. **STT (Securities Transaction Tax)**: 0.025% on SELL orders for equity intraday; 0.1% on delivery.
3. **Exchange Turnover Charges**: NSE charges ~0.00297% on total turnover.
4. **GST (Goods & Services Tax)**: 18% levied on `Brokerage + Exchange Charges + SEBI Charges`.
5. **SEBI Turnover Fees**: ₹10 per crore (0.0001% of turnover).
6. **Stamp Duty**: 0.003% on BUY turnover.
7. **Slippage**: Configurable percentage (default 0.05%) representing bid-ask spread and market impact.

## Factual Quantitative Performance Metrics
- **CAGR**: Compound Annual Growth Rate over the backtest duration.
- **Profit Factor**: Gross Profits divided by Gross Losses.
- **Sharpe Ratio**: Annualized excess return relative to the Indian 10-Year Government Bond (G-Sec) risk-free rate (~6.5%).
- **Sortino Ratio**: Downside volatility adjusted return.
- **Maximum Drawdown**: Maximum percentage drop from equity peak to subsequent trough.
