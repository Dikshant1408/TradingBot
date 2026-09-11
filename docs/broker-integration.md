# Indian Broker Integration & Regulatory Review (Section 54 Compliance)

This document provides a factual, non-speculative engineering and regulatory evaluation of Indian retail algorithmic trading broker APIs for personal quantitative trading.

---

## 1. Candidate Indian Broker APIs

| Broker | API Name | API Pricing (Monthly) | Authentication Method | Retail Algo Approval Required? | Static IP Required? | Rate Limits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Zerodha** | Kite Connect API v3 | ₹2,000 / month (+ ₹2,000 for Historical) | API Key + API Secret + Daily OAuth Request Token + TOTP | No for personal manual-trigger; Yes for automated institutional | No | 3 orders/sec, 10 req/sec |
| **Angel One** | SmartAPI | **Free** for retail clients | API Key + Client ID + MPIN + TOTP (automated JWT via PyOTP) | No for personal retail API | No | 10 req/sec |
| **Shoonya (Finvasia)**| Shoonya API | **Free** zero brokerage / zero API fee | User ID + Password + TOTP + Vendor Key | No for personal retail API | No | Standard rate limits |
| **Upstox** | Upstox API v2 | Free basic / charges for advanced feeds | OAuth 2.0 + Daily Login Redirection | No for personal retail API | No | Standard rate limits |
| **Dhan** | DhanHQ SuperFast API | **Free** for all Dhan account holders | Access Token + 2FA / Webhook | No for personal retail API | No | 10 req/sec |

---

## 2. Proposed Primary Integration: Angel One SmartAPI or Zerodha Kite Connect

### Why Angel One SmartAPI is Recommended for Personal Bots:
1. **Cost**: SmartAPI is 100% free for retail accounts (Zerodha charges ₹2,000 to ₹4,000 per month).
2. **Headless Authentication**: Supports headless TOTP generation (via RFC 6238 TOTP seed), meaning personal bots running locally on Windows do not require manual daily browser OAuth redirection.
3. **Official Python SDK**: `smartapi-python` maintained with active REST & WebSocket support.
4. **Exchange Support**: NSE, BSE, NFO, MCX.

### Why Zerodha Kite Connect is the Standard Institutional Benchmark:
1. Highly robust, stable, battle-tested infrastructure.
2. Strict daily OAuth login requirement: Each morning around 08:30 AM, the user must log in via a browser URL to generate an exchange-mandated `request_token`, which is then exchanged for a 24-hour `access_token`.

---

## 3. Current Regulatory Framework (SEBI & Indian Exchanges)

### SEBI Algorithmic Trading Directives for Retail Clients:
- **Exchange Audit & Strategy Approval**: SEBI circulars mandate that algorithmic strategies hosted by brokers for client-side automated execution must have exchange approval. However, **API-based retail trading where an individual trader places orders via their own personal API key** operates under the retail API framework.
- **Order Tagging**: Orders placed via APIs are tagged with specific vendor/algo tags by the broker gateway before submission to the exchange.
- **Kill-Switch Mandate**: Brokers provide user-level kill switches via their mobile/web apps to square off all positions if a retail algorithm malfunctions.
- **Trading Hours**: Standard equity market hours are 09:15 to 15:30 IST. Pre-open session is 09:00 to 09:08 IST.

---

## 4. Credentials & Prerequisites Checklist

To connect a live broker adapter, you must possess:
1. Active Demat and Trading account with the broker.
2. Registered Developer App on the broker's developer portal.
3. `API_KEY` and `API_SECRET`.
4. Client User ID and PIN/Password.
5. TOTP authentication key (Authenticator QR seed).

---

## 5. Safety Execution Boundary in this Bot

Under no circumstances should live broker credentials be activated until:
1. The user has thoroughly backtested the strategy across multiple market regimes.
2. The user has run the strategy in **Paper Trading Replay Mode** on local simulated market data.
3. Preflight check returns `all_passed: true`.
4. Double confirmation has been manually accepted.
