/**
 * QuantDesk India - Plotly Chart Rendering Engine
 */
const ChartEngine = {
  renderPlotlyJson: (elementId, plotlyJson) => {
    if (!plotlyJson || !plotlyJson.data) return;
    const config = {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
      displaylogo: false
    };

    Plotly.newPlot(elementId, plotlyJson.data, plotlyJson.layout, config);
  },

  renderMiniEquityCurve: (elementId, equityHistory) => {
    if (!equityHistory || equityHistory.length === 0) return;
    const x = equityHistory.map(e => e.timestamp);
    const y = equityHistory.map(e => e.equity);

    const trace = {
      x: x,
      y: y,
      mode: 'lines',
      line: { color: '#00c087', width: 2 },
      fill: 'tozeroy',
      fillcolor: 'rgba(0, 192, 135, 0.08)'
    };

    const layout = {
      template: 'plotly_dark',
      paper_bgcolor: '#10141a',
      plot_bgcolor: '#10141a',
      font: { family: 'JetBrains Mono, monospace', color: '#8b949e', size: 10 },
      margin: { l: 40, r: 20, t: 20, b: 30 },
      xaxis: { gridcolor: '#1c242e' },
      yaxis: { gridcolor: '#1c242e' }
    };

    Plotly.newPlot(elementId, [trace], layout, { responsive: true, displayModeBar: false });
  }
};
