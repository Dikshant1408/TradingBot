# QuantDesk India: Private Quantitative Trading Workstation

> **Notice:** This is a **private personal trading workstation for local use on Windows**. It is strictly for individual quantitative research, backtesting, paper trading, and risk-managed execution. It is **NOT** a commercial SaaS platform, social network, or public subscription service.

---

## 1. Overview & Capabilities

QuantDesk India is an algorithmic trading workstation built specifically for Indian financial markets (NSE/BSE).

### Core Features:
- **Three Strict Operating Modes**:
  - `BACKTEST`: Historical event-driven simulation with zero lookahead bias.
  - `PAPER`: Real-time simulated execution with virtual capital and realistic Indian tax/brokerage modeling.
  - `LIVE`: Real exchange trading (strictly locked and disabled by default; requires multiple confirmations and pre-flight validation).
- **Indian Market Realistic Cost Simulator**:
  - Brokerage (flat ₹20 or percentage)
  - STT (Securities Transaction Tax)
  - Exchange Turnover Charges (NSE ~0.00297%)
  - GST (18%)
  - SEBI Turnover Charges (₹10/crore)
  - Stamp Duty (0.003% intraday buy)
  - Configurable Slippage (default 0.05%)
- **Safety Architecture**:
  - Big Prominent **EMERGENCY STOP** Button.
  - Max Daily Loss Guardrail (e.g. ₹5,000 max loss halts trading).
  - Max Drawdown Limit (e.g. 5% max drawdown halts trading).
  - Max Trades Per Day (e.g. 5 trades/day threshold).
  - Duplicate Order Suppression within cooldown window.
  - Persistent SQLite Kill Switch.
- **Serious Quantitative Terminal UI**:
  - Professional dark aesthetic inspired by Bloomberg Terminal and Zerodha Kite.
  - Interactive Plotly Candlestick charts with BUY/SELL trade execution markers.
  - Dual-axis interactive Equity Curve and Underwater Drawdown graphs.
  - Real-time WebSocket telemetry.
  - Tabular trade logs with CSV export.

---

## 2. Windows Installation & Quick Start

### Prerequisites:
- Windows 10 or 11
- Python 3.10, 3.11, or 3.12 installed ([python.org](https://www.python.org/downloads/))
  - *Ensure "Add python.exe to PATH" was checked during installation.*

### Easy Method: Double-Click Batch File
Double-click:
```text
start_bot.bat
```
This script automatically sets up `.venv`, installs dependencies, launches the server, and opens `http://127.0.0.1:8000` in your default web browser.

### Manual Setup via PowerShell / Command Prompt:
```powershell
# 1. Clone or navigate to the repository
cd "d:\Projects\Startup Ideas\Trading Bot"

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate the environment
.\.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python run.py
```

The terminal interface will be accessible at:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 3. Command Line Interface (CLI)

You can also run quick backtests and status checks directly from the command line:

```powershell
# Check current market session, bot mode, and capital
python -m app.cli status

# Run a backtest from terminal
python -m app.cli backtest --strategy MA_Crossover --symbol NIFTY50_DEMO --fast 15 --slow 40 --capital 100000
```

---

## 4. Workstation Navigation Guide

1. **Dashboard**: Live market clock (IST), session status (Open/Closed), virtual cash, today's P&L, mark-to-market positions, and risk utilization gauges.
2. **Backtest**: Select Indian instrument, choose Fast & Slow MA periods, configure starting capital, run event-driven simulation, and inspect interactive candlestick trade markers, equity curve, drawdown, and trade logs. Export trades to CSV.
3. **Strategies**: View strategy parameter definitions, mathematical validation rules, and logic description.
4. **Paper Trading**: Replay historical bars sequentially with configurable speed or step bar-by-bar to test strategy execution without risk.
5. **Portfolio**: Summary of virtual balances, invested margin, and position risk.
6. **Trades**: Complete audit log of all completed round-trip trades.
7. **Risk Controls**: Set maximum daily loss, max drawdown, and max trades per day. Toggle the persistent Kill Switch or trigger Emergency Stop.
8. **Market Data**: Inspect Indian instruments catalog (NSE equities, indices, lot sizes, tick sizes), upload custom CSV datasets, or generate clean synthetic demo datasets.
9. **Settings & Logs**: Inspect active configuration (with secrets redacted), review live trading pre-flight checklist, and view rotating application logs.

---

## 5. Security & Safety Guarantee

- **No Remote Access**: The server strictly binds to `127.0.0.1`.
- **Secret Redaction**: Passwords, tokens, and API keys are automatically masked from all logs and API responses.
- **Physical Separation**: Backtesting and Paper Trading modules have **zero** code paths capable of placing live broker orders.
- **Section 54 Regulatory Review**: Review [docs/broker-integration.md](docs/broker-integration.md) before connecting any real broker account.

---

## 6. How to Stop the Bot

- **Emergency Stop**: Click the prominent red **🛑 EMERGENCY STOP** button in the top header. The bot will instantly halt all execution, lock order placement, and require manual user inspection to reset.
- **Shut Down Server**: Press `Ctrl + C` in the terminal window running `run.py`.
