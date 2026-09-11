/**
 * QuantDesk India - API Client
 */
const API = {
  // System
  getHealth: () => fetch('/api/system/health').then(r => r.json()),
  getSettings: () => fetch('/api/system/settings').then(r => r.json()),
  getLogs: (lines = 100) => fetch(`/api/system/logs?lines=${lines}`).then(r => r.json()),

  // Market
  getInstruments: () => fetch('/api/market/instruments').then(r => r.json()),
  getMarketStatus: () => fetch('/api/market/status').then(r => r.json()),
  getMarketData: (symbol, limit = 50) => fetch(`/api/market/data/${symbol}?limit=${limit}`).then(r => r.json()),
  generateDemoData: (symbol = 'NIFTY50_DEMO', days = 180) =>
    fetch(`/api/market/generate-demo?symbol=${symbol}&days=${days}`, { method: 'POST' }).then(r => r.json()),
  uploadCSV: (formData) =>
    fetch('/api/market/upload', { method: 'POST', body: formData }).then(r => r.json()),

  // Strategy
  getStrategies: () => fetch('/api/strategy/list').then(r => r.json()),

  // Backtest
  runBacktest: (payload) =>
    fetch('/api/backtest/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(async r => {
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || 'Backtest failed');
      }
      return r.json();
    }),
  getBacktestHistory: () => fetch('/api/backtest/history').then(r => r.json()),
  getBacktestDetails: (id) => fetch(`/api/backtest/${id}`).then(r => r.json()),

  // Paper Trading
  getPaperStatus: () => fetch('/api/paper/status').then(r => r.json()),
  configurePaper: (payload) =>
    fetch('/api/paper/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(async r => {
      if (!r.ok) throw new Error((await r.json()).detail);
      return r.json();
    }),
  startPaper: () => fetch('/api/paper/start', { method: 'POST' }).then(r => r.json()),
  pausePaper: () => fetch('/api/paper/pause', { method: 'POST' }).then(r => r.json()),
  stopPaper: () => fetch('/api/paper/stop', { method: 'POST' }).then(r => r.json()),
  stepPaper: () => fetch('/api/paper/step', { method: 'POST' }).then(async r => {
    if (!r.ok) throw new Error((await r.json()).detail);
    return r.json();
  }),
  getPaperPositions: () => fetch('/api/paper/positions').then(r => r.json()),
  getPaperOrders: () => fetch('/api/paper/orders').then(r => r.json()),
  getPaperTrades: () => fetch('/api/paper/trades').then(r => r.json()),

  // Risk & Safety Controls
  getRiskStatus: () => fetch('/api/risk/limits').then(r => r.json()),
  updateRiskLimits: (payload) =>
    fetch('/api/risk/limits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()),
  toggleKillSwitch: (active) =>
    fetch('/api/risk/kill-switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active })
    }).then(r => r.json()),
  triggerEmergencyStop: (reason) =>
    fetch('/api/risk/emergency-stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    }).then(r => r.json()),
  resetEmergencyStop: () => fetch('/api/risk/emergency-reset', { method: 'POST' }).then(r => r.json()),

  // Live Trading Gate
  getLivePreflight: () => fetch('/api/live/preflight').then(r => r.json()),
  confirmLiveTrading: (payload) =>
    fetch('/api/live/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(async r => {
      if (!r.ok) throw new Error((await r.json()).detail);
      return r.json();
    }),
  revokeLiveTrading: () => fetch('/api/live/revoke', { method: 'POST' }).then(r => r.json()),

  // Walk-forward & Monte Carlo
  runWalkForward: (payload) =>
    fetch('/api/backtest/walk-forward', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(async r => {
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || 'Walk-forward failed');
      }
      return r.json();
    }),
  getMonteCarlo: (runId) => fetch(`/api/backtest/${runId}/monte-carlo`).then(r => r.json()),

  // Audit Trail
  getAuditTrail: (limit = 100) => fetch(`/api/system/audit-trail?limit=${limit}`).then(r => r.json())
};
