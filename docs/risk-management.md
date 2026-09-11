# Risk Management & Capital Preservation Guardrails

The Risk Engine serves as an uncompromising gatekeeper evaluating every order intent prior to submission.

## Safety Checkpoints

1. **Emergency Stop (Prominent Header Button)**:
   - When engaged, the bot enters `EMERGENCY_STOPPED` status.
   - All strategy processing is suspended.
   - Any open or pending orders are halted.
   - Telegram notification is immediately dispatched.
   - Manual user inspection and reset are required to resume.

2. **Maximum Daily Loss (₹ INR)**:
   - If cumulative daily P&L drops below `-MAX_DAILY_LOSS`, the bot is marked as `HALTED`.
   - Further opening orders are rejected.

3. **Maximum Drawdown (%)**:
   - If portfolio equity drops below `(1 - MAX_DRAWDOWN_PERCENT) * Peak_Equity`, trading is halted.

4. **Maximum Trades Per Day**:
   - Hard threshold (e.g. 5 trades/day) to prevent churn or over-trading in choppy markets.

5. **Duplicate Order Suppression**:
   - Compares symbol, side, quantity, and recent timestamps.
   - Suppresses repeated order submissions within the cooldown window (default 10 seconds).

6. **Persistent Kill Switch**:
   - Stored in SQLite database.
   - If `kill_switch = true`, any live order submission is rejected at the API level.
