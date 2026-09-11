# Paper Trading & Simulated Broker

Paper trading enables realistic rehearsal of strategies without risking real capital.

## Operating Modes
1. **Historical Replay Mode**: Step through historical datasets candle by candle at a configurable interval (e.g. 0.5 seconds per candle) or manually with the "STEP 1 BAR" button.
2. **Polling Mode**: Polls market prices during active Indian exchange hours (09:15 to 15:30 IST).

## Simulated Broker Features
- Virtual Cash balance (default ₹100,000 INR, customizable).
- Real-time mark-to-market unrealized P&L calculation.
- Realistic order book tracking (BUY, SELL, EXIT).
- Indian statutory transaction costs and slippage deducted from virtual cash.
- Position sizing constrained by instrument lot sizes (e.g., NIFTY lot size of 25).
