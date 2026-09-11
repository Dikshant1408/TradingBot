/**
 * QuantDesk India - Terminal Controller Application
 */
document.addEventListener('DOMContentLoaded', () => {
  // Navigation Tabs
  const tabs = document.querySelectorAll('.nav-tab');
  const panes = document.querySelectorAll('.tab-pane');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      tabs.forEach(t => t.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const targetPane = document.getElementById(`pane-${target}`);
      if (targetPane) targetPane.classList.add('active');

      // Refresh specific tab data on view
      if (target === 'paper') loadPaperStatus();
      if (target === 'portfolio') loadPortfolioData();
      if (target === 'trades') loadTradesData();
      if (target === 'risk') loadRiskData();
      if (target === 'data') loadMarketDataTab();
      if (target === 'settings') loadSettingsAndLogs();
      if (target === 'strategies') loadStrategiesTab();
    });
  });

  // Emergency Stop Buttons
  const emergencyStopBtn = document.getElementById('btn-emergency-stop');
  const emergencyStopRiskBtn = document.getElementById('btn-emergency-stop-risk');
  const emergencyResetBtn = document.getElementById('btn-emergency-reset');

  const triggerEmergencyStop = async () => {
    if (confirm('CRITICAL ACTION: Immediately HALT the trading bot, prevent orders, and require manual restart?')) {
      try {
        await API.triggerEmergencyStop('User clicked EMERGENCY STOP on terminal header');
        await syncSystemHealth();
        alert('EMERGENCY STOP ENGAGED. All strategy executions halted.');
      } catch (err) {
        alert('Error triggering emergency stop: ' + err.message);
      }
    }
  };

  if (emergencyStopBtn) emergencyStopBtn.addEventListener('click', triggerEmergencyStop);
  if (emergencyStopRiskBtn) emergencyStopRiskBtn.addEventListener('click', triggerEmergencyStop);

  if (emergencyResetBtn) {
    emergencyResetBtn.addEventListener('click', async () => {
      if (confirm('Reset emergency stop and return system to IDLE?')) {
        await API.resetEmergencyStop();
        await syncSystemHealth();
      }
    });
  }

  // Initial Data Sync
  syncSystemHealth();
  syncMarketStatus();
  loadInstrumentsDropdown();
  loadStrategiesDropdown();
  loadBacktestHistory();
  loadRiskData();

  // Periodic Polling
  setInterval(syncMarketStatus, 15000);
  setInterval(syncSystemHealth, 5000);

  // WebSocket Telemetry Client
  const wsClient = new WebSocketClient((msg) => {
    if (msg.state) {
      updateTopTelemetry(msg.state);
    }
    if (msg.type === 'STATUS_CHANGED' || msg.type === 'EMERGENCY_STOP' || msg.type === 'RISK_ALERT') {
      syncSystemHealth();
      loadPaperStatus();
    }
  });

  // --- Header & Global Status ---
  async function syncSystemHealth() {
    try {
      const h = await API.getHealth();
      const modeBadge = document.getElementById('mode-badge');
      const botStatusEl = document.getElementById('telemetry-status');
      const emergencyBanner = document.getElementById('emergency-banner');

      if (modeBadge) {
        modeBadge.textContent = `● ${h.mode}`;
        modeBadge.className = `mode-badge mode-${h.mode.toLowerCase()}`;
      }

      if (botStatusEl) {
        botStatusEl.textContent = h.bot_status;
        botStatusEl.className = h.bot_status === 'RUNNING' ? 'telemetry-val positive' :
                               (h.bot_status === 'HALTED' || h.bot_status === 'EMERGENCY_STOPPED') ? 'telemetry-val negative' : 'telemetry-val';
      }

      if (emergencyBanner) {
        if (h.is_emergency_stopped) {
          emergencyBanner.style.display = 'flex';
          emergencyBanner.textContent = '🚨 EMERGENCY STOP ENGAGED: Trading operations halted. Click Risk tab to inspect or reset.';
        } else if (h.is_kill_switch_active) {
          emergencyBanner.style.display = 'flex';
          emergencyBanner.textContent = '🔒 KILL SWITCH ACTIVE: Order placement strictly disabled in database/settings.';
        } else {
          emergencyBanner.style.display = 'none';
        }
      }
    } catch (e) {
      console.error('Health sync failed', e);
    }
  }

  async function syncMarketStatus() {
    try {
      const s = await API.getMarketStatus();
      const clockEl = document.getElementById('telemetry-clock');
      const marketStateEl = document.getElementById('telemetry-market');

      if (clockEl) clockEl.textContent = s.current_ist;
      if (marketStateEl) {
        marketStateEl.textContent = s.is_open ? 'OPEN' : 'CLOSED';
        marketStateEl.className = s.is_open ? 'telemetry-val positive' : 'telemetry-val negative';
      }
    } catch (e) {}
  }

  function updateTopTelemetry(state) {
    const cashEl = document.getElementById('telemetry-cash');
    const pnlEl = document.getElementById('telemetry-pnl');
    const ddEl = document.getElementById('telemetry-drawdown');

    if (cashEl && state.cash !== undefined) cashEl.textContent = `₹${state.cash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    if (pnlEl && state.today_pnl !== undefined) {
      const val = state.today_pnl;
      pnlEl.textContent = `${val >= 0 ? '+' : ''}₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      pnlEl.className = val >= 0 ? 'telemetry-val positive' : 'telemetry-val negative';
    }
    if (ddEl && state.drawdown_pct !== undefined) {
      ddEl.textContent = `${(state.drawdown_pct * 100).toFixed(2)}%`;
    }
  }

  // --- Dropdowns ---
  async function loadInstrumentsDropdown() {
    try {
      const list = await API.getInstruments();
      const selects = [document.getElementById('bt-instrument'), document.getElementById('paper-instrument')];
      selects.forEach(sel => {
        if (!sel) return;
        sel.innerHTML = '';
        list.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.symbol;
          opt.textContent = `${item.symbol} (${item.exchange} - ${item.name})`;
          sel.appendChild(opt);
        });
      });
    } catch (e) {}
  }

  async function loadStrategiesDropdown() {
    try {
      const list = await API.getStrategies();
      const selects = [document.getElementById('bt-strategy'), document.getElementById('paper-strategy')];
      selects.forEach(sel => {
        if (!sel) return;
        sel.innerHTML = '';
        list.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.id;
          opt.textContent = `${item.name} (v${item.version})`;
          sel.appendChild(opt);
        });
      });
    } catch (e) {}
  }

  // --- Backtest Tab ---
  const btForm = document.getElementById('backtest-form');
  if (btForm) {
    btForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('btn-run-backtest');
      btn.disabled = true;
      btn.textContent = 'RUNNING BACKTEST...';

      const payload = {
        strategy_id: document.getElementById('bt-strategy').value,
        symbol: document.getElementById('bt-instrument').value,
        initial_capital: parseFloat(document.getElementById('bt-capital').value),
        position_size_pct: parseFloat(document.getElementById('bt-pos-size').value) / 100,
        brokerage: parseFloat(document.getElementById('bt-brokerage').value),
        slippage_pct: parseFloat(document.getElementById('bt-slippage').value) / 100,
        parameters: {
          fast_period: parseInt(document.getElementById('bt-fast-ma').value),
          slow_period: parseInt(document.getElementById('bt-slow-ma').value),
          ma_type: document.getElementById('bt-ma-type').value,
          direction: document.getElementById('bt-direction').value
        }
      };

      try {
        const res = await API.runBacktest(payload);
        renderBacktestResults(res);
        loadBacktestHistory();
      } catch (err) {
        alert('Backtest failed: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'RUN BACKTEST';
      }
    });
  }

  function renderBacktestResults(res) {
    document.getElementById('bt-results-container').style.display = 'block';
    const m = res.metrics;

    document.getElementById('kpi-initial-cap').textContent = `₹${m.initial_capital.toLocaleString('en-IN')}`;
    document.getElementById('kpi-final-cap').textContent = `₹${m.final_capital.toLocaleString('en-IN')}`;
    
    const pnlEl = document.getElementById('kpi-net-pnl');
    pnlEl.textContent = `${m.net_pnl >= 0 ? '+' : ''}₹${m.net_pnl.toLocaleString('en-IN')} (${m.return_pct}%)`;
    pnlEl.className = m.net_pnl >= 0 ? 'card-value positive' : 'card-value negative';

    document.getElementById('kpi-win-rate').textContent = `${m.win_rate}% (${m.winning_trades}W / ${m.losing_trades}L)`;
    document.getElementById('kpi-profit-factor').textContent = m.profit_factor;
    document.getElementById('kpi-max-dd').textContent = `${m.max_drawdown}% (₹${m.max_drawdown_amount.toLocaleString('en-IN')})`;
    document.getElementById('kpi-sharpe').textContent = m.sharpe_ratio;
    document.getElementById('kpi-fees').textContent = `₹${m.total_fees.toLocaleString('en-IN')}`;
    document.getElementById('kpi-slippage').textContent = `₹${m.slippage_cost.toLocaleString('en-IN')}`;

    // Plotly Candlestick & Trade Markers
    ChartEngine.renderPlotlyJson('bt-candlestick-chart', res.candlestick_chart);
    // Plotly Equity Curve
    ChartEngine.renderPlotlyJson('bt-equity-chart', res.equity_chart);

    // Trades Table
    const tbody = document.getElementById('bt-trades-table-body');
    tbody.innerHTML = '';
    res.trades.forEach((t, idx) => {
      const row = document.createElement('tr');
      const pnlClass = t.net_pnl >= 0 ? 'positive' : 'negative';
      row.innerHTML = `
        <td>${idx + 1}</td>
        <td>${t.entry_time.replace('T', ' ').substring(0, 19)}</td>
        <td>${t.symbol}</td>
        <td><span class="badge ${t.side === 'LONG' ? 'positive' : 'negative'}">${t.side}</span></td>
        <td>${t.quantity}</td>
        <td>₹${t.entry_price.toFixed(2)}</td>
        <td>₹${t.exit_price ? t.exit_price.toFixed(2) : '-'}</td>
        <td class="${pnlClass}">${t.net_pnl >= 0 ? '+' : ''}₹${t.net_pnl.toFixed(2)}</td>
        <td>₹${t.total_fees.toFixed(2)}</td>
        <td style="color: #8b949e;">${t.strategy_reason || ''}</td>
      `;
      tbody.appendChild(row);
    });

    const exportBtn = document.getElementById('btn-export-bt-csv');
    if (exportBtn) {
      exportBtn.onclick = () => {
        window.open(`/api/backtest/${res.id}/export-csv`, '_blank');
      };
    }
  }

  async function loadBacktestHistory() {
    try {
      const history = await API.getBacktestHistory();
      const tbody = document.getElementById('bt-history-table-body');
      if (!tbody) return;
      tbody.innerHTML = '';
      history.forEach(h => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${h.strategy_name}</td>
          <td>${h.symbol}</td>
          <td class="${h.net_pnl >= 0 ? 'positive' : 'negative'}">${h.return_pct}%</td>
          <td>${h.win_rate}%</td>
          <td>${h.max_drawdown}%</td>
          <td>${h.sharpe_ratio}</td>
          <td><button class="btn" style="padding: 2px 6px; font-size: 11px;" onclick="loadPastBacktest('${h.id}')">View</button></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {}
  }

  window.loadPastBacktest = async (id) => {
    try {
      const res = await API.getBacktestDetails(id);
      renderBacktestResults(res);
      window.scrollTo({ top: 350, behavior: 'smooth' });
    } catch (e) {
      alert('Failed to load past backtest');
    }
  };

  // --- Paper Trading Tab ---
  const btnPaperConfig = document.getElementById('btn-paper-configure');
  const btnPaperStart = document.getElementById('btn-paper-start');
  const btnPaperPause = document.getElementById('btn-paper-pause');
  const btnPaperStop = document.getElementById('btn-paper-stop');
  const btnPaperStep = document.getElementById('btn-paper-step');

  if (btnPaperConfig) {
    btnPaperConfig.addEventListener('click', async () => {
      const payload = {
        strategy_id: document.getElementById('paper-strategy').value,
        symbol: document.getElementById('paper-instrument').value,
        initial_capital: parseFloat(document.getElementById('paper-capital').value),
        replay_delay_seconds: parseFloat(document.getElementById('paper-speed').value),
        parameters: {
          fast_period: parseInt(document.getElementById('paper-fast-ma').value),
          slow_period: parseInt(document.getElementById('paper-slow-ma').value)
        }
      };
      try {
        await API.configurePaper(payload);
        alert('Paper trading configured.');
        loadPaperStatus();
      } catch (err) {
        alert('Configuration error: ' + err.message);
      }
    });
  }

  if (btnPaperStart) {
    btnPaperStart.addEventListener('click', async () => {
      try {
        await API.startPaper();
        loadPaperStatus();
      } catch (err) {
        alert('Start failed: ' + err.message);
      }
    });
  }

  if (btnPaperPause) {
    btnPaperPause.addEventListener('click', async () => {
      await API.pausePaper();
      loadPaperStatus();
    });
  }

  if (btnPaperStop) {
    btnPaperStop.addEventListener('click', async () => {
      await API.stopPaper();
      loadPaperStatus();
    });
  }

  if (btnPaperStep) {
    btnPaperStep.addEventListener('click', async () => {
      try {
        await API.stepPaper();
        loadPaperStatus();
      } catch (err) {
        alert('Step failed: ' + err.message);
      }
    });
  }

  async function loadPaperStatus() {
    try {
      const s = await API.getPaperStatus();
      document.getElementById('paper-cash-display').textContent = `₹${s.account.cash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      document.getElementById('paper-equity-display').textContent = `₹${s.account.total_equity.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      
      const pnlEl = document.getElementById('paper-pnl-display');
      pnlEl.textContent = `${s.account.today_pnl >= 0 ? '+' : ''}₹${s.account.today_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      pnlEl.className = s.account.today_pnl >= 0 ? 'card-value positive' : 'card-value negative';

      document.getElementById('paper-progress-text').textContent = `Bar ${s.current_bar} / ${s.total_bars}`;

      // Load Orders & Positions
      const positions = await API.getPaperPositions();
      const posBody = document.getElementById('paper-positions-body');
      if (posBody) {
        posBody.innerHTML = '';
        if (positions.length === 0) {
          posBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #57606a;">No open positions</td></tr>';
        } else {
          positions.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td>${p.symbol}</td>
              <td><span class="${p.side === 'LONG' ? 'positive' : 'negative'}">${p.side}</span></td>
              <td>${p.quantity}</td>
              <td>₹${p.entry_price.toFixed(2)}</td>
              <td>₹${p.current_price.toFixed(2)}</td>
              <td class="${p.unrealized_pnl >= 0 ? 'positive' : 'negative'}">${p.unrealized_pnl >= 0 ? '+' : ''}₹${p.unrealized_pnl.toFixed(2)}</td>
              <td>${p.stop_loss ? '₹' + p.stop_loss : '-'} / ${p.target ? '₹' + p.target : '-'}</td>
            `;
            posBody.appendChild(tr);
          });
        }
      }

      const orders = await API.getPaperOrders();
      const ordBody = document.getElementById('paper-orders-body');
      if (ordBody) {
        ordBody.innerHTML = '';
        orders.slice(0, 15).forEach(o => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${o.timestamp.replace('T', ' ').substring(11, 19)}</td>
            <td>${o.symbol}</td>
            <td class="${o.side === 'BUY' ? 'positive' : 'negative'}">${o.side}</td>
            <td>${o.quantity}</td>
            <td>₹${o.price.toFixed(2)}</td>
            <td>${o.status}</td>
            <td style="color: #8b949e;">${o.reason || ''}</td>
          `;
          ordBody.appendChild(tr);
        });
      }
    } catch (e) {}
  }

  // --- Portfolio & Positions Tab ---
  async function loadPortfolioData() {
    loadPaperStatus();
  }

  // --- Trades Tab ---
  async function loadTradesData() {
    try {
      const trades = await API.getPaperTrades();
      const tbody = document.getElementById('all-trades-body');
      if (!tbody) return;
      tbody.innerHTML = '';
      if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #57606a;">No trades completed yet</td></tr>';
        return;
      }
      trades.forEach((t, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${i + 1}</td>
          <td>${t.symbol}</td>
          <td class="${t.side === 'LONG' ? 'positive' : 'negative'}">${t.side}</td>
          <td>${t.quantity}</td>
          <td>₹${t.entry_price.toFixed(2)}</td>
          <td>₹${t.exit_price ? t.exit_price.toFixed(2) : '-'}</td>
          <td class="${t.net_pnl >= 0 ? 'positive' : 'negative'}">${t.net_pnl >= 0 ? '+' : ''}₹${t.net_pnl.toFixed(2)}</td>
          <td>₹${t.total_fees.toFixed(2)}</td>
          <td>${t.exit_time ? t.exit_time.substring(0, 19).replace('T', ' ') : '-'}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {}
  }

  // --- Risk Tab ---
  async function loadRiskData() {
    try {
      const r = await API.getRiskStatus();
      document.getElementById('risk-daily-loss').value = r.limits.max_daily_loss;
      document.getElementById('risk-drawdown').value = (r.limits.max_drawdown_pct * 100);
      document.getElementById('risk-max-trades').value = r.limits.max_trades_per_day;
      document.getElementById('risk-pos-size').value = r.limits.max_position_size_value;
      document.getElementById('risk-open-pos').value = r.limits.max_open_positions;

      const u = r.utilization;
      document.getElementById('gauge-daily-loss').textContent = `₹${u.daily_loss.current} / ₹${u.daily_loss.limit} (${u.daily_loss.pct}%)`;
      document.getElementById('gauge-drawdown').textContent = `${u.drawdown.current}% / ${u.drawdown.limit}% (${u.drawdown.pct}%)`;
      document.getElementById('gauge-trades').textContent = `${u.trades_count.current} / ${u.trades_count.limit} (${u.trades_count.pct}%)`;

      const ksBtn = document.getElementById('btn-kill-switch-toggle');
      if (ksBtn) {
        ksBtn.textContent = r.is_kill_switch_active ? 'DISABLE KILL SWITCH' : 'ACTIVATE KILL SWITCH';
        ksBtn.className = r.is_kill_switch_active ? 'btn btn-success' : 'btn btn-danger';
        ksBtn.onclick = async () => {
          const activate = !r.is_kill_switch_active;
          if (confirm(`Are you sure you want to ${activate ? 'ACTIVATE' : 'DEACTIVATE'} the Kill Switch?`)) {
            await API.toggleKillSwitch(activate);
            loadRiskData();
            syncSystemHealth();
          }
        };
      }
    } catch (e) {}
  }

  const riskForm = document.getElementById('risk-limits-form');
  if (riskForm) {
    riskForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        max_daily_loss: parseFloat(document.getElementById('risk-daily-loss').value),
        max_drawdown_pct: parseFloat(document.getElementById('risk-drawdown').value) / 100,
        max_trades_per_day: parseInt(document.getElementById('risk-max-trades').value),
        max_position_size_value: parseFloat(document.getElementById('risk-pos-size').value),
        max_open_positions: parseInt(document.getElementById('risk-open-pos').value)
      };
      await API.updateRiskLimits(payload);
      alert('Risk limits updated.');
      loadRiskData();
    });
  }

  // --- Market Data Tab ---
  async function loadMarketDataTab() {
    try {
      const list = await API.getInstruments();
      const tbody = document.getElementById('catalog-table-body');
      if (!tbody) return;
      tbody.innerHTML = '';
      list.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${item.symbol}</b></td>
          <td>${item.name}</td>
          <td>${item.exchange}</td>
          <td>${item.instrument_type}</td>
          <td>${item.lot_size}</td>
          <td>₹${item.tick_size}</td>
          <td>${item.trading_hours}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {}
  }

  const uploadForm = document.getElementById('csv-upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('csv-file-input');
      const symbolInput = document.getElementById('csv-symbol-input');
      if (!fileInput.files.length) return alert('Select a CSV file first');

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('symbol', symbolInput.value.toUpperCase());

      try {
        const res = await API.uploadCSV(formData);
        alert(res.message);
        loadInstrumentsDropdown();
      } catch (err) {
        alert('Upload failed: ' + err.message);
      }
    });
  }

  const btnGenDemo = document.getElementById('btn-generate-demo-data');
  if (btnGenDemo) {
    btnGenDemo.addEventListener('click', async () => {
      try {
        const res = await API.generateDemoData('NIFTY50_DEMO', 180);
        alert(res.message + '\nNote: ' + res.compliance_note);
      } catch (err) {
        alert('Generation failed: ' + err.message);
      }
    });
  }

  // --- Settings & Logs Tab ---
  async function loadSettingsAndLogs() {
    try {
      const s = await API.getSettings();
      const preflight = await API.getLivePreflight();
      const settingsBox = document.getElementById('settings-dump-box');
      if (settingsBox) settingsBox.textContent = JSON.stringify(s, null, 2);

      const preflightBox = document.getElementById('preflight-status-box');
      if (preflightBox) {
        preflightBox.innerHTML = `
          <div style="font-weight: bold; margin-bottom: 8px;">Mode: ${preflight.mode.toUpperCase()} | Locked: ${preflight.is_locked ? 'YES (SAFE)' : 'UNLOCKED'}</div>
          <div>✓ App Mode 'live': ${preflight.checklist.mode_is_live ? 'YES' : 'NO (Disabled by default)'}</div>
          <div>✓ Credentials configured: ${preflight.checklist.credentials_present ? 'YES' : 'NO'}</div>
          <div>✓ Double confirmation: ${preflight.checklist.double_confirmation_accepted ? 'YES' : 'NO'}</div>
          <div>✓ Kill Switch inactive: ${preflight.checklist.kill_switch_inactive ? 'YES' : 'NO'}</div>
          <div>✓ Risk limits valid: ${preflight.checklist.risk_limits_configured ? 'YES' : 'NO'}</div>
          <div style="margin-top: 10px; color: #8b949e; font-size: 11px;">${preflight.regulatory_notice}</div>
        `;
      }

      const logData = await API.getLogs(100);
      const logTerminal = document.getElementById('log-terminal-box');
      if (logTerminal) {
        logTerminal.textContent = logData.logs.join('');
        logTerminal.scrollTop = logTerminal.scrollHeight;
      }
    } catch (e) {}
  }

  const btnRefreshLogs = document.getElementById('btn-refresh-logs');
  if (btnRefreshLogs) {
    btnRefreshLogs.addEventListener('click', loadSettingsAndLogs);
  }

  // --- Strategies Tab ---
  async function loadStrategiesTab() {
    try {
      const list = await API.getStrategies();
      const container = document.getElementById('strategies-catalog-container');
      if (!container) return;
      container.innerHTML = '';
      list.forEach(s => {
        const div = document.createElement('div');
        div.className = 'card';
        div.style.marginBottom = '12px';
        div.innerHTML = `
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-size: 14px; font-weight: bold; color: #58a6ff;">${s.name} (v${s.version})</span>
            <span class="brand-badge">ID: ${s.id}</span>
          </div>
          <p style="color: #8b949e; margin-bottom: 8px;">${s.description}</p>
          <div style="font-size: 11px; background: #0b0e11; padding: 8px; border-radius: 3px;">
            <b>Parameters:</b> ${JSON.stringify(s.parameters)}
          </div>
        `;
        container.appendChild(div);
      });
    } catch (e) {}
  }
});
