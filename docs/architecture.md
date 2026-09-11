# System Architecture & Technical Design

QuantDesk India is designed as a single-tenant, private local quantitative trading workstation for Indian markets (NSE/BSE).

## Core Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                 Browser Quant Terminal UI                   │
│   Dashboard | Backtest | Paper | Risk | Data | Logs         │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST API + WebSockets
┌──────────────────────────────┴──────────────────────────────┐
│                    FastAPI Application                      │
│   Routers: /api/market, /api/backtest, /api/paper,          │
│            /api/risk, /api/live, /api/system                │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
┌──────────────┴───────────────┐ ┌─────────────┴──────────────┐
│      Core Trading Engine     │ │       Risk Management      │
│  - Clock (09:15-15:30 IST)   │ │  - Max Daily Loss (₹)      │
│  - State Machine             │ │  - Max Drawdown (%)        │
│  - EventBus (Pub/Sub)        │ │  - Max Trades / Day        │
│  - Strategy Framework        │ │  - Duplicate Order Filter  │
│                              │ │  - Emergency Stop Button   │
└──────────────┬───────────────┘ └─────────────┬──────────────┘
               │                               │
┌──────────────┴───────────────────────────────┴──────────────┐
│             Execution Layer (Mode Isolation)                │
│  ┌───────────────────────────┬───────────────────────────┐  │
│  │   BacktestBroker          │   PaperBroker             │  │
│  │   - Chronological Fills   │   - Virtual Account Cash  │  │
│  │   - Indian Tax Simulator  │   - Mark-to-Market PnL    │  │
│  │   - Slippage Modeling     │   - Order Book & Fills    │  │
│  └───────────────────────────┴───────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │   LiveBroker (LOCKED by default)                      │  │
│  │   - Pre-flight Gatekeeper & Confirmation Modal        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Security & Privacy Principles
1. **Localhost Binding**: Binds exclusively to `127.0.0.1:8000`. No external exposure.
2. **Secret Redaction**: API keys and tokens are scrubbed from logs and sanitized in API outputs.
3. **Physical Mode Separation**: Backtest and Paper brokers have no live exchange communication pathways.
