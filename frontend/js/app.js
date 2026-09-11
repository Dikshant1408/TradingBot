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
      if (target === 'research') loadExperiments();
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

      const execModelEl = document.getElementById('bt-exec-model');
      const segmentEl = document.getElementById('bt-segment');

      const brokerProfileEl = document.getElementById('bt-broker-profile');

      const payload = {
        strategy_id: document.getElementById('bt-strategy').value,
        symbol: document.getElementById('bt-instrument').value,
        initial_capital: parseFloat(document.getElementById('bt-capital').value),
        position_size_pct: parseFloat(document.getElementById('bt-pos-size').value) / 100,
        brokerage: parseFloat(document.getElementById('bt-brokerage').value),
        slippage_pct: parseFloat(document.getElementById('bt-slippage').value) / 100,
        execution_model: execModelEl ? execModelEl.value : 'NEXT_OPEN',
        segment: segmentEl ? segmentEl.value : 'EQUITY_INTRADAY',
        broker_profile: brokerProfileEl ? brokerProfileEl.value : 'ZERODHA',
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

  // Walk-Forward Analysis Handler
  const btnWalkForward = document.getElementById('btn-run-walk-forward');
  if (btnWalkForward) {
    btnWalkForward.addEventListener('click', async () => {
      btnWalkForward.disabled = true;
      btnWalkForward.textContent = 'ANALYZING...';
      const execModelEl = document.getElementById('bt-exec-model');
      const segmentEl = document.getElementById('bt-segment');

      const payload = {
        strategy_id: document.getElementById('bt-strategy').value,
        symbol: document.getElementById('bt-instrument').value,
        initial_capital: parseFloat(document.getElementById('bt-capital').value),
        execution_model: execModelEl ? execModelEl.value : 'NEXT_OPEN',
        segment: segmentEl ? segmentEl.value : 'EQUITY_INTRADAY',
        parameters: {
          fast_period: parseInt(document.getElementById('bt-fast-ma').value),
          slow_period: parseInt(document.getElementById('bt-slow-ma').value),
          ma_type: document.getElementById('bt-ma-type').value,
          direction: document.getElementById('bt-direction').value
        },
        in_sample_pct: 0.65,
        rolling_windows: 4
      };

      try {
        const wfRes = await API.runWalkForward(payload);
        renderWalkForwardModal(wfRes);
      } catch (err) {
        alert('Walk-Forward Analysis failed: ' + err.message);
      } finally {
        btnWalkForward.disabled = false;
        btnWalkForward.textContent = 'WALK-FORWARD (OOS)';
      }
    });
  }

  window._currentBacktestTrades = [];

  function renderBacktestResults(res) {
    document.getElementById('bt-results-container').style.display = 'block';
    const m = res.metrics;
    window._currentBacktestTrades = res.trades || [];

    // 1. Anti-Bias Diagnostics
    const diag = res.diagnostics;
    if (diag) {
      const scoreEl = document.getElementById('bt-robustness-score');
      if (scoreEl) {
        scoreEl.textContent = `${diag.robustness_score}/100`;
        scoreEl.className = `diag-score ${diag.robustness_score >= 80 ? '' : diag.robustness_score >= 50 ? 'med' : 'low'}`;
      }

      const statusEl = document.getElementById('bt-diag-status');
      if (statusEl) {
        statusEl.innerHTML = diag.is_statistically_sound
          ? '<span class="diag-badge diag-badge-clean">✓ ROBUST & STATISTICALLY SOUND</span>'
          : '<span class="diag-badge diag-badge-warn">⚠️ BIAS / CURVE-FIT WARNINGS DETECTED</span>';
      }

      const badgesEl = document.getElementById('bt-diag-badges');
      if (badgesEl) {
        badgesEl.innerHTML = (diag.checks_passed || []).map(c => 
          `<span class="diag-badge diag-badge-clean">✓ ${c.replace(/_/g, ' ')}</span>`
        ).join(' ');
      }

      const warnEl = document.getElementById('bt-diag-warnings');
      if (warnEl) {
        if (diag.warnings && diag.warnings.length > 0) {
          warnEl.innerHTML = diag.warnings.map(w => `<div style="margin-top: 4px;">⚠️ ${w}</div>`).join('');
        } else {
          warnEl.innerHTML = '<div style="color: var(--color-green); font-size: 11px;">All institutional robustness checks cleared (Zero lookahead, sufficient sample, non-fitted parameters).</div>';
        }
      }
    }

    // 2. High-Level Metrics
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
    const brokerProfileLabel = document.getElementById('kpi-broker-profile');
    if (brokerProfileLabel) {
      const profileEl = document.getElementById('bt-broker-profile');
      brokerProfileLabel.textContent = profileEl ? profileEl.options[profileEl.selectedIndex].text : '';
    }

    // 2b. Quality Score Subscores
    const qbdEl = document.getElementById('bt-quality-breakdown');
    if (qbdEl && res.diagnostics && res.diagnostics.subscores) {
      qbdEl.style.display = 'grid';
      const ss = res.diagnostics.subscores;
      const setSubscore = (id, val) => {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = val !== undefined ? `${val}/100` : '--';
          el.className = 'quality-subscore-val' + (val >= 80 ? ' positive' : val >= 50 ? ' neutral' : ' negative');
        }
      };
      setSubscore('qbd-sample', ss.sample_size);
      setSubscore('qbd-exec', ss.execution_realism);
      setSubscore('qbd-cost', ss.cost_impact);
      setSubscore('qbd-dd', ss.drawdown_resilience);
    }

    // 3. Plotly Candlestick & Equity Curves
    ChartEngine.renderPlotlyJson('bt-candlestick-chart', res.candlestick_chart);
    ChartEngine.renderPlotlyJson('bt-equity-chart', res.equity_chart);

    // 4. Monte Carlo Simulation
    const mc = res.monte_carlo;
    if (mc) {
      const mcSummaryEl = document.getElementById('bt-monte-carlo-summary');
      if (mcSummaryEl) mcSummaryEl.textContent = `${mc.simulations_count || 1000} paths generated`;

      const medRetEl = document.getElementById('mc-median-ret');
      if (medRetEl) medRetEl.textContent = `${mc.median_return_pct}%`;

      const p5RetEl = document.getElementById('mc-p5-ret');
      if (p5RetEl) p5RetEl.textContent = `${mc.p5_return_pct}%`;

      const p95DdEl = document.getElementById('mc-p95-dd');
      if (p95DdEl) p95DdEl.textContent = `${mc.p95_drawdown_pct}%`;

      const ruinEl = document.getElementById('mc-ruin-risk');
      if (ruinEl) ruinEl.textContent = `${mc.risk_of_ruin_pct}%`;

      if (mc.plot_json) {
        ChartEngine.renderPlotlyJson('bt-monte-carlo-chart', mc.plot_json);
      }
    }

    // 5. Long vs Short Breakdown
    const lsBody = document.getElementById('bt-long-short-body');
    if (lsBody && m.long_short_stats) {
      lsBody.innerHTML = '';
      ['LONG', 'SHORT'].forEach(side => {
        const s = m.long_short_stats[side];
        if (!s) return;
        const tr = document.createElement('tr');
        const pnlCls = s.net_pnl >= 0 ? 'positive' : 'negative';
        tr.innerHTML = `
          <td><span class="badge ${side === 'LONG' ? 'positive' : 'negative'}">${side}</span></td>
          <td>${s.trades_count}</td>
          <td>${s.win_rate}%</td>
          <td class="${pnlCls}">${s.net_pnl >= 0 ? '+' : ''}₹${s.net_pnl.toFixed(2)}</td>
          <td>${s.profit_factor}</td>
        `;
        lsBody.appendChild(tr);
      });
    }

    // 6. Day of Week Breakdown
    const dowBody = document.getElementById('bt-dow-body');
    if (dowBody && m.day_of_week_stats) {
      dowBody.innerHTML = '';
      Object.keys(m.day_of_week_stats).forEach(day => {
        const d = m.day_of_week_stats[day];
        const tr = document.createElement('tr');
        const pnlCls = d.net_pnl >= 0 ? 'positive' : 'negative';
        tr.innerHTML = `
          <td style="font-weight: 600;">${day}</td>
          <td>${d.trades_count}</td>
          <td>${d.win_rate}%</td>
          <td class="${pnlCls}">${d.net_pnl >= 0 ? '+' : ''}₹${d.net_pnl.toFixed(2)}</td>
        `;
        dowBody.appendChild(tr);
      });
    }

    // 7. Monthly Performance Matrix
    const monthBody = document.getElementById('bt-monthly-body');
    if (monthBody && m.monthly_matrix) {
      monthBody.innerHTML = '';
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      Object.keys(m.monthly_matrix).sort().reverse().forEach(yr => {
        const yData = m.monthly_matrix[yr] || {};
        const tr = document.createElement('tr');
        let cellsHtml = `<td style="font-weight: 700; color: #fff;">${yr}</td>`;
        months.forEach(mo => {
          const val = yData[mo];
          if (val === undefined || val === null) {
            cellsHtml += `<td class="perf-cell-zero">-</td>`;
          } else {
            const cls = val > 0 ? 'perf-cell-pos' : val < 0 ? 'perf-cell-neg' : 'perf-cell-zero';
            cellsHtml += `<td class="${cls}">${val > 0 ? '+' : ''}${val}%</td>`;
          }
        });
        const ytd = yData['YTD'] || 0;
        const ytdCls = ytd > 0 ? 'perf-cell-pos' : ytd < 0 ? 'perf-cell-neg' : 'perf-cell-zero';
        cellsHtml += `<td class="${ytdCls}" style="font-weight: bold; border-left: 1px solid var(--border-color);">${ytd > 0 ? '+' : ''}${ytd}%</td>`;
        tr.innerHTML = cellsHtml;
        monthBody.appendChild(tr);
      });
    }

    // 8. Trades Table with "Why?" Forensics Button
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
        <td style="color: #8b949e; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t.strategy_reason || ''}</td>
        <td><button class="btn" style="padding: 2px 8px; font-size: 10px; border-color: var(--color-blue); color: var(--color-blue);" onclick="window.inspectTrade(${idx})">Why?</button></td>
      `;
      tbody.appendChild(row);
    });

    const exportBtn = document.getElementById('btn-export-bt-csv');
    if (exportBtn) {
      exportBtn.onclick = () => {
        window.open(`/api/backtest/${res.id}/export-csv`, '_blank');
      };
    }

    // Wire Save Experiment button
    const saveExpBtn = document.getElementById('btn-save-experiment');
    if (saveExpBtn) {
      saveExpBtn.onclick = async () => {
        const name = prompt('Experiment name (e.g. "MA20/50 NIFTY 2023"):', `${res.metrics?.strategy_name || 'Strategy'} @ ${new Date().toLocaleDateString('en-IN')}`);
        if (!name) return;
        const tags = prompt('Tags (comma-separated, optional):', '') || '';
        const hypothesis = prompt('Hypothesis (optional, 1 sentence):', '') || '';
        try {
          const payload = {
            name,
            backtest_id: res.id,
            symbol: document.getElementById('bt-instrument').value,
            strategy_id: document.getElementById('bt-strategy').value,
            hypothesis,
            tags: tags.split(',').map(t => t.trim()).filter(Boolean),
            metrics: res.metrics,
            parameters: res.parameters
          };
          await API.saveExperiment(payload);
          alert(`Experiment "${name}" saved! View it in the Research tab.`);
        } catch (err) {
          alert('Failed to save: ' + err.message);
        }
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
          <div>✓ Hard Flag 'LIVE_TRADING_ENABLED': ${preflight.hard_flag_enabled ? 'TRUE' : 'FALSE (Safe by default)'}</div>
          <div>✓ Process Session Authorized: ${preflight.process_authorized ? 'YES (Ephemeral)' : 'NO (Expires on reboot)'}</div>
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

      // Forensic Audit Trail
      const auditData = await API.getAuditTrail(50);
      const auditBody = document.getElementById('audit-trail-body');
      if (auditBody && auditData.audit_logs) {
        auditBody.innerHTML = '';
        if (auditData.audit_logs.length === 0) {
          auditBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #57606a;">No audit records found</td></tr>';
        } else {
          auditData.audit_logs.forEach(a => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td style="color: var(--text-secondary);">${a.timestamp ? a.timestamp.replace('T', ' ').substring(0, 19) : '-'}</td>
              <td><span class="badge ${a.actor === 'USER' ? 'positive' : 'negative'}">${a.actor}</span></td>
              <td style="font-weight: 600; color: #fff;">${a.action}</td>
              <td style="color: var(--color-blue);">${a.component}</td>
              <td style="font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${JSON.stringify(a.details)}
              </td>
            `;
            auditBody.appendChild(tr);
          });
        }
      }
    } catch (e) {}
  }

  const btnRefreshLogs = document.getElementById('btn-refresh-logs');
  if (btnRefreshLogs) {
    btnRefreshLogs.addEventListener('click', loadSettingsAndLogs);
  }

  const btnRefreshAudit = document.getElementById('btn-refresh-audit');
  if (btnRefreshAudit) {
    btnRefreshAudit.addEventListener('click', loadSettingsAndLogs);
  }

  // --- Trade Diagnostics ("Why Did the Bot Trade?") ---
  window.inspectTrade = (idx) => {
    const trade = window._currentBacktestTrades[idx];
    if (!trade) return;

    const modal = document.getElementById('modal-trade-why');
    const content = document.getElementById('modal-why-content');
    if (!modal || !content) return;

    let snap = {};
    if (trade.indicator_snapshot) {
      if (typeof trade.indicator_snapshot === 'string') {
        try { snap = JSON.parse(trade.indicator_snapshot); } catch (e) { snap = {}; }
      } else {
        snap = trade.indicator_snapshot;
      }
    }

    const pnlCls = trade.net_pnl >= 0 ? 'positive' : 'negative';
    const grossPnl = ((trade.exit_price || 0) - trade.entry_price) * trade.quantity * (trade.side === 'LONG' ? 1 : -1);

    content.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px;">
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Symbol & Side</div>
          <div style="font-weight: bold; color: #fff; font-size: 14px;">${trade.symbol} <span class="badge ${trade.side === 'LONG' ? 'positive' : 'negative'}">${trade.side}</span></div>
        </div>
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Entry / Exit Price</div>
          <div style="font-weight: bold; color: #fff; font-size: 14px;">₹${trade.entry_price.toFixed(2)} → ₹${trade.exit_price ? trade.exit_price.toFixed(2) : '-'}</div>
        </div>
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Gross vs Net P&L</div>
          <div style="font-weight: bold; font-size: 14px;" class="${pnlCls}">₹${grossPnl.toFixed(2)} → ₹${trade.net_pnl.toFixed(2)}</div>
        </div>
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Total Friction (Taxes/Fees)</div>
          <div style="font-weight: bold; color: var(--color-amber); font-size: 14px;">₹${trade.total_fees.toFixed(2)}</div>
        </div>
      </div>

      <div style="background: #0d1219; border: 1px solid var(--border-color); border-radius: 4px; padding: 14px; margin-bottom: 16px;">
        <div style="font-weight: bold; color: var(--color-blue); margin-bottom: 6px; font-size: 13px;">🎯 Execution Reason & Logic Trigger</div>
        <div style="color: #e6edf3; font-size: 13px; line-height: 1.5;">${trade.strategy_reason || 'Signal generated from indicator threshold event.'}</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 6px;">
          Timestamps: Entry <b>${trade.entry_time.replace('T', ' ')}</b> | Exit <b>${trade.exit_time ? trade.exit_time.replace('T', ' ') : 'Open'}</b>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div class="card">
          <div class="card-title">📈 Quantitative Indicator Snapshot at Signal</div>
          <div style="margin-top: 8px;">
            ${Object.keys(snap).length === 0 ? '<div style="color: var(--text-muted); font-size: 11px;">No indicator metadata captured for this legacy trade.</div>' : `
              <table class="terminal-table">
                <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                <tbody>
                  ${Object.entries(snap).map(([k, v]) => `
                    <tr>
                      <td style="color: var(--text-secondary); font-family: var(--font-mono);">${k}</td>
                      <td style="font-weight: bold; color: #fff; font-family: var(--font-mono);">${typeof v === 'number' ? v.toFixed(3) : v}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            `}
          </div>
        </div>

        <div class="card">
          <div class="card-title">🇮🇳 Indian Statutory Cost & Friction Breakdown</div>
          <div style="margin-top: 8px;">
            <table class="terminal-table">
              <thead><tr><th>Statutory Component</th><th>Amount</th></tr></thead>
              <tbody>
                <tr><td>Brokerage (₹20/order max)</td><td style="font-weight: bold;">₹${((trade.brokerage || 40.0)).toFixed(2)}</td></tr>
                <tr><td>STT (Securities Transaction Tax)</td><td style="font-weight: bold;">₹${((trade.stt || 0)).toFixed(2)}</td></tr>
                <tr><td>Exchange Turnover Charges (NSE)</td><td style="font-weight: bold;">₹${((trade.exchange_charges || 0)).toFixed(2)}</td></tr>
                <tr><td>GST (18% on Brokerage & Exchange)</td><td style="font-weight: bold;">₹${((trade.gst || 0)).toFixed(2)}</td></tr>
                <tr><td>SEBI Regulatory Turnover Fee</td><td style="font-weight: bold;">₹${((trade.sebi_charges || 0)).toFixed(2)}</td></tr>
                <tr><td>Stamp Duty (State Level)</td><td style="font-weight: bold;">₹${((trade.stamp_duty || 0)).toFixed(2)}</td></tr>
                <tr><td>Simulated Slippage</td><td style="font-weight: bold;">₹${((trade.slippage || 0)).toFixed(2)}</td></tr>
                <tr style="border-top: 1px solid var(--border-highlight); font-weight: bold; color: var(--color-amber);">
                  <td>Total Statutory Drag</td><td>₹${trade.total_fees.toFixed(2)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    modal.style.display = 'flex';
  };

  // --- Walk-Forward Results Modal ---
  function renderWalkForwardModal(res) {
    const modal = document.getElementById('modal-walk-forward');
    const content = document.getElementById('modal-wf-content');
    if (!modal || !content) return;

    const summary = res.summary || {};
    const windows = res.windows || [];

    content.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Overall Robustness</div>
          <div style="font-size: 16px; font-weight: bold; color: ${summary.is_robust ? 'var(--color-green)' : 'var(--color-amber)'};">
            ${summary.is_robust ? '✓ ROBUST' : '⚠️ OVERFIT RISK'}
          </div>
        </div>
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Walk-Forward Efficiency (WFE)</div>
          <div style="font-size: 16px; font-weight: bold; color: #fff;">${summary.walk_forward_efficiency_pct}%</div>
        </div>
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Average In-Sample Return</div>
          <div style="font-size: 16px; font-weight: bold; color: var(--color-blue);">${summary.avg_in_sample_return_pct}%</div>
        </div>
        <div style="background: #10141a; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
          <div style="color: var(--text-muted); font-size: 11px;">Average Out-of-Sample Return</div>
          <div style="font-size: 16px; font-weight: bold; color: ${summary.avg_out_of_sample_return_pct >= 0 ? 'var(--color-green)' : 'var(--color-red)'};">
            ${summary.avg_out_of_sample_return_pct}%
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Rolling Validation Slices (Train vs Test)</div>
        <div class="table-container" style="margin-top: 8px;">
          <table class="terminal-table">
            <thead>
              <tr>
                <th>Slice</th>
                <th>In-Sample (Train) Period</th>
                <th>IS Net Return</th>
                <th>IS Trades</th>
                <th>Out-of-Sample (Test) Period</th>
                <th>OOS Net Return</th>
                <th>OOS Trades</th>
                <th>Efficiency (OOS/IS)</th>
              </tr>
            </thead>
            <tbody>
              ${windows.map(w => {
                const effCls = w.efficiency_ratio >= 0.5 ? 'positive' : w.efficiency_ratio > 0 ? 'color: var(--color-amber);' : 'negative';
                return `
                  <tr>
                    <td><b>Slice #${w.window_index}</b></td>
                    <td>${w.is_start} → ${w.is_end}</td>
                    <td class="${w.is_return_pct >= 0 ? 'positive' : 'negative'}">${w.is_return_pct >= 0 ? '+' : ''}${w.is_return_pct}%</td>
                    <td>${w.is_trades}</td>
                    <td>${w.oos_start} → ${w.oos_end}</td>
                    <td class="${w.oos_return_pct >= 0 ? 'positive' : 'negative'}">${w.oos_return_pct >= 0 ? '+' : ''}${w.oos_return_pct}%</td>
                    <td>${w.oos_trades}</td>
                    <td class="${effCls}">${(w.efficiency_ratio * 100).toFixed(1)}%</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;

    modal.style.display = 'flex';
  }

  // Close Modals
  const btnCloseWhy = document.getElementById('btn-close-why-modal');
  if (btnCloseWhy) {
    btnCloseWhy.onclick = () => {
      document.getElementById('modal-trade-why').style.display = 'none';
    };
  }

  const btnCloseWf = document.getElementById('btn-close-wf-modal');
  if (btnCloseWf) {
    btnCloseWf.onclick = () => {
      document.getElementById('modal-walk-forward').style.display = 'none';
    };
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

  // --- Research & Experiments Tab ---
  async function loadExperiments() {
    const tbody = document.getElementById('experiments-table-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:#57606a;">Loading...</td></tr>';
    try {
      const list = await API.getExperiments();
      if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:#57606a;">No experiments saved yet. Run a backtest and click "Save as Experiment".</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      list.forEach(exp => {
        const m = exp.metrics || {};
        const pnlCls = (m.return_pct || 0) >= 0 ? 'positive' : 'negative';
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-weight:700; color:#58a6ff;">${exp.name || '-'}</td>
          <td>${exp.symbol || '-'}</td>
          <td>${exp.strategy_id || '-'}</td>
          <td class="${pnlCls}">${m.return_pct !== undefined ? (m.return_pct >= 0 ? '+' : '') + m.return_pct + '%' : '-'}</td>
          <td>${m.sharpe_ratio !== undefined ? m.sharpe_ratio : '-'}</td>
          <td>${m.win_rate !== undefined ? m.win_rate + '%' : '-'}</td>
          <td>${m.max_drawdown !== undefined ? m.max_drawdown + '%' : '-'}</td>
          <td>${m.total_trades !== undefined ? m.total_trades : '-'}</td>
          <td style="color:#8b949e; font-size:11px;">${(exp.tags || []).join(', ')}</td>
          <td style="color:#8b949e;">${exp.created_at ? new Date(exp.created_at).toLocaleDateString('en-IN') : '-'}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:var(--color-red);">Failed to load experiments.</td></tr>';
    }
  }

  const btnRefreshExperiments = document.getElementById('btn-refresh-experiments');
  if (btnRefreshExperiments) {
    btnRefreshExperiments.addEventListener('click', loadExperiments);
  }
});
