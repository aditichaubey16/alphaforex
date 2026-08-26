const state = { currentSymbol: null };

// ---- pair avatars (generated monogram from the base currency) ----

const AVATAR_PALETTE = ["#5b7fff", "#8b6bff", "#22a6b3", "#2fbf74", "#eaad3f", "#ef5a63", "#d4af6a", "#3f8ee0"];

function avatarInitials(symbol) {
  return (symbol || "??").replace("=X", "").slice(0, 2).toUpperCase();
}

function avatarColor(symbol) {
  let hash = 0;
  for (let i = 0; i < (symbol || "").length; i++) hash = symbol.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function avatarHtml(symbol, size = "md") {
  const initials = avatarInitials(symbol);
  const bg = avatarColor(symbol);
  return `<div class="avatar avatar-${size}" style="background:${bg};">${initials}</div>`;
}

// ---- generic chart helpers (plain CSS/SVG, no library) ----

function stackBarHtml(segments) {
  const clean = segments.filter((s) => s.value > 0);
  const total = clean.reduce((sum, s) => sum + s.value, 0) || 1;
  const bar = clean.map((s) => `<div class="stackbar-seg" style="width:${(s.value / total) * 100}%;background:${s.color};"></div>`).join("");
  const legend = clean
    .map((s) => `<div class="stackbar-legend-item"><span class="dot" style="background:${s.color};"></span>${s.label} <b>${s.value}</b></div>`)
    .join("");
  return `<div class="stackbar">${bar}</div><div class="stackbar-legend">${legend}</div>`;
}

// `extraSeries` (optional): [{key, color, label}] — additional fields on each
// point (e.g. sma20/sma50/sma200) overlaid as plain polylines with a legend,
// on top of the primary interactive `close` line.
let _lineChartSeq = 0;
function renderLineChart(container, points, quoteCurrency, extraSeries) {
  if (!points || points.length < 2) {
    container.innerHTML = '<div class="empty">Not enough price history available.</div>';
    return;
  }
  const W = 640, H = 200, padTop = 14, padBottom = 26, plotH = H - padTop - padBottom;
  const allValues = points.flatMap((p) => [p.close, ...(extraSeries || []).map((s) => p[s.key])]).filter((v) => v !== null && v !== undefined);
  const min = Math.min(...allValues), max = Math.max(...allValues);
  const range = max - min || 1;
  const n = points.length;
  const xAt = (i) => (i / (n - 1)) * W;
  const yAt = (v) => padTop + (1 - (v - min) / range) * plotH;

  // Two joins of the same coordinates: "L"-separated for the <path> area
  // fill (SVG path syntax), plain-space-separated for the <polyline> (its
  // "points" attribute is a bare coordinate list — "L" is not valid there).
  const pathPoints = points.map((p, i) => `${xAt(i).toFixed(2)},${yAt(p.close).toFixed(2)}`).join(" L");
  const linePoints = points.map((p, i) => `${xAt(i).toFixed(2)},${yAt(p.close).toFixed(2)}`).join(" ");
  const areaPath = `M0,${(padTop + plotH).toFixed(2)} L${pathPoints} L${W},${(padTop + plotH).toFixed(2)} Z`;
  const gradId = `lc-grad-${++_lineChartSeq}`;

  const first = points[0], last = points[points.length - 1];
  const changePct = first.close ? ((last.close - first.close) / first.close) * 100 : 0;
  const lineColor = changePct >= 0 ? "var(--green)" : "var(--red)";
  const ccy = quoteCurrency ? ` ${quoteCurrency}` : "";

  const overlayLines = (extraSeries || [])
    .map((s) => {
      const pts = points
        .map((p, i) => (p[s.key] !== null && p[s.key] !== undefined ? `${xAt(i).toFixed(2)},${yAt(p[s.key]).toFixed(2)}` : null))
        .filter(Boolean);
      if (pts.length < 2) return "";
      return `<polyline points="${pts.join(" ")}" fill="none" stroke="${s.color}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" opacity="0.9"></polyline>`;
    })
    .join("");
  const legend = extraSeries
    ? `<div class="chart-legend">
        <div class="chart-legend-item"><span class="swatch" style="background:${lineColor};"></span>Price</div>
        ${extraSeries.map((s) => `<div class="chart-legend-item"><span class="swatch" style="background:${s.color};"></span>${s.label}</div>`).join("")}
      </div>`
    : "";

  container.innerHTML = `
    <div class="line-chart-wrap">
      <svg class="line-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${changePct >= 0 ? "#2fbf74" : "#ef5a63"}" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="${changePct >= 0 ? "#2fbf74" : "#ef5a63"}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${areaPath}" fill="url(#${gradId})" stroke="none"></path>
        ${overlayLines}
        <polyline points="${linePoints}" fill="none" stroke="${lineColor}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"></polyline>
        <circle class="lc-endpoint" cx="${xAt(n - 1)}" cy="${yAt(last.close)}" r="4" fill="${lineColor}" stroke="var(--bg-elevated)" stroke-width="2"></circle>
        <line class="lc-crosshair" x1="0" y1="${padTop}" x2="0" y2="${padTop + plotH}" stroke="var(--border)" stroke-width="1" opacity="0"></line>
        <circle class="lc-hover-dot" r="4" fill="${lineColor}" stroke="var(--bg-elevated)" stroke-width="2" opacity="0"></circle>
      </svg>
      <div class="line-chart-tooltip"><div class="lct-date"></div><div class="lct-price"></div></div>
    </div>
    ${legend}
    <div class="range-endlabels" style="margin-top:2px;">
      <span>${first.date}</span>
      <span style="color:${changePct >= 0 ? "var(--green)" : "var(--red)"};font-weight:600;">${changePct >= 0 ? "+" : ""}${changePct.toFixed(1)}% over period</span>
      <span>${last.date}</span>
    </div>
  `;

  const svg = container.querySelector(".line-chart-svg");
  const crosshair = container.querySelector(".lc-crosshair");
  const hoverDot = container.querySelector(".lc-hover-dot");
  const tooltip = container.querySelector(".line-chart-tooltip");

  function onMove(evt) {
    const rect = svg.getBoundingClientRect();
    const relX = ((evt.clientX - rect.left) / rect.width) * W;
    const idx = Math.max(0, Math.min(n - 1, Math.round((relX / W) * (n - 1))));
    const px = xAt(idx), py = yAt(points[idx].close);
    crosshair.setAttribute("x1", px);
    crosshair.setAttribute("x2", px);
    crosshair.setAttribute("opacity", "1");
    hoverDot.setAttribute("cx", px);
    hoverDot.setAttribute("cy", py);
    hoverDot.setAttribute("opacity", "1");
    tooltip.querySelector(".lct-date").textContent = points[idx].date;
    tooltip.querySelector(".lct-price").textContent = `${fmt(points[idx].close, 5)}${ccy}`;
    tooltip.classList.add("visible");
    tooltip.style.left = `${(px / W) * rect.width}px`;
    tooltip.style.top = `${(py / H) * rect.height}px`;
  }
  function onLeave() {
    crosshair.setAttribute("opacity", "0");
    hoverDot.setAttribute("opacity", "0");
    tooltip.classList.remove("visible");
  }
  svg.addEventListener("mousemove", onMove);
  svg.addEventListener("mouseleave", onLeave);
}

// Colors picked to stay distinct from the price line, which is dynamically
// green/red depending on period trend — none of these overlap either.
const SMA_OVERLAY_SERIES = [
  { key: "sma20", color: "var(--gold)", label: "SMA20" },
  { key: "sma50", color: "#8b6bff", label: "SMA50" },
  { key: "sma200", color: "var(--accent-strong)", label: "SMA200" },
];

// ---- field descriptions (hover tooltips) ----

const DESCRIPTIONS = {
  "Price": "Last traded rate for this pair.",
  "Day Change %": "Change vs the previous session's close.",
  "1W Change %": "Change over the trailing 5 trading sessions.",
  "1M Change %": "Change over the trailing ~22 trading sessions.",
  "SMA20": "20-day simple moving average — short-term trend.",
  "SMA50": "50-day simple moving average — medium-term trend.",
  "SMA200": "200-day simple moving average — long-term trend. Needs ~200 days of history to populate.",
  "RSI14": "Relative Strength Index over 14 days. Above 70 is commonly read as overbought, below 30 as oversold.",
  "MACD": "Moving Average Convergence Divergence — MACD line minus its 9-day signal line. Positive means bullish momentum.",
  "ATR14": "Average True Range over 14 days — average daily trading range, a volatility measure used to size stops/positions.",
  "52W Range": "Lowest and highest price over the past year — gives a sense of where the current price sits in its recent range.",
  "Previous Close": "Closing price on the last trading session.",
  "Day Change %.raw": "Change vs the previous session's close.",
  "1-Week Change %": "Change over the trailing 5 trading sessions.",
  "1-Month Change %": "Change over the trailing ~22 trading sessions.",
  "Day High": "Highest price traded so far in the current session.",
  "Day Low": "Lowest price traded so far in the current session.",
  "52-Week High": "Highest price in the past year of daily bars.",
  "52-Week Low": "Lowest price in the past year of daily bars.",
  "SMA 20": "20-day simple moving average of closing price — short-term trend.",
  "SMA 50": "50-day simple moving average of closing price — medium-term trend.",
  "SMA 200": "200-day simple moving average of closing price — long-term trend.",
  "Price vs SMA20 %": "How far the current price sits above (+) or below (-) its 20-day average.",
  "Price vs SMA50 %": "How far the current price sits above (+) or below (-) its 50-day average.",
  "Price vs SMA200 %": "How far the current price sits above (+) or below (-) its 200-day average.",
  "RSI (14)": "Relative Strength Index over 14 days — 0 to 100. Above 70 commonly read as overbought, below 30 as oversold.",
  "MACD Line": "12-day EMA minus 26-day EMA of closing price.",
  "MACD Signal": "9-day EMA of the MACD line — the trigger line for crossover signals.",
  "MACD Histogram": "MACD line minus signal line. Positive and rising means strengthening bullish momentum.",
  "ATR (14)": "Average True Range over 14 days, in price terms — average size of a day's trading range.",
  "ATR as % of Price": "ATR expressed as a percentage of the current price — comparable across pairs with very different price levels.",
};

function tipAttrs(label, baseClass) {
  const desc = DESCRIPTIONS[label];
  const cls = desc ? [baseClass, "has-tip"].filter(Boolean).join(" ") : baseClass;
  const clsAttr = cls ? ` class="${cls}"` : "";
  const tipAttr = desc ? ` data-tip="${desc.replace(/"/g, "&quot;")}"` : "";
  return clsAttr + tipAttr;
}

// ---- helpers ----

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

function fmt(n, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (typeof n !== "number") return n;
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
  return n.toFixed(digits);
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  document.getElementById(`view-${name}`).classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  const btn = document.querySelector(`.nav-btn[data-view="${name}"]`);
  if (btn) btn.classList.add("active");
}

// ---- shared pair list cache (used by the Calendar's pair select) ----

let _pairsCache = null;
async function getPairs() {
  if (_pairsCache) return _pairsCache;
  _pairsCache = await api("/api/pairs");
  return _pairsCache;
}

// ---- pairs view: group tiles -> market-watch table ----

const GROUP_META = {
  Majors: { sub: "The 7 most-traded pairs" },
  "INR Crosses": { sub: "Each major against the Indian Rupee" },
};

async function showPairGroups() {
  document.getElementById("pairs-table-panel").classList.add("hidden");
  document.getElementById("pairs-groups-panel").classList.remove("hidden");
  state.currentGroup = null;

  const box = document.getElementById("group-cards");
  box.innerHTML = "";
  const pairs = await getPairs();
  const groups = {};
  pairs.forEach((p) => {
    if (!groups[p.group]) groups[p.group] = [];
    groups[p.group].push(p);
  });

  Object.entries(groups).forEach(([groupName, groupPairs]) => {
    const meta = GROUP_META[groupName] || {};
    const badges = groupPairs.slice(0, 4).map((p) => avatarHtml(p.symbol, "sm")).join("");
    const card = el(`
      <div class="group-card">
        <div class="group-card-top">
          <div class="currency-badges">${badges}</div>
          <span class="mw-live-badge"><span class="live-dot"></span>Live</span>
        </div>
        <div class="group-title">${groupName}</div>
        <div class="group-sub">${meta.sub || ""}</div>
        <div class="group-footer">
          <span class="group-count">${groupPairs.length} pairs</span>
          <span class="group-arrow">View rates &rarr;</span>
        </div>
      </div>
    `);
    card.addEventListener("click", () => loadGroupTable(groupName));
    box.appendChild(card);
  });
}

async function loadGroupTable(groupName) {
  state.currentGroup = groupName;
  document.getElementById("pairs-groups-panel").classList.add("hidden");
  const tablePanel = document.getElementById("pairs-table-panel");
  tablePanel.classList.remove("hidden");
  document.getElementById("pairs-table-title").textContent = groupName;

  const box = document.getElementById("pairs-table");
  box.innerHTML = '<div class="empty">Loading…</div>';
  const pairs = (await getPairs()).filter((p) => p.group === groupName);

  const table = el(`
    <table class="mw-table">
      <thead><tr><th>Pair</th><th>Open</th><th>High</th><th>Low</th><th>Last</th><th>Chg %</th><th>Call</th></tr></thead>
      <tbody></tbody>
    </table>
  `);
  const tbody = table.querySelector("tbody");
  box.innerHTML = "";
  box.appendChild(table);

  pairs.forEach((p) => {
    const row = el(`
      <tr>
        <td style="text-align:left;"><span class="row-with-avatar">${avatarHtml(p.symbol, "sm")}<span class="symbol">${p.base}/${p.quote}</span></span></td>
        <td class="mw-open">…</td>
        <td class="mw-high">…</td>
        <td class="mw-low">…</td>
        <td class="mw-last">…</td>
        <td class="mw-chg">…</td>
        <td><span class="rec-badge rec-pill">…</span></td>
      </tr>
    `);
    row.addEventListener("click", () => openPair(p.symbol));
    tbody.appendChild(row);

    api(`/api/pair/${encodeURIComponent(p.symbol)}`)
      .then((data) => {
        const s = data.snapshot;
        const chgClass = s.change_pct > 0 ? "mw-up" : s.change_pct < 0 ? "mw-down" : "";
        row.querySelector(".mw-open").textContent = s.open_today !== null && s.open_today !== undefined ? fmt(s.open_today, 5) : fmt(s.prev_close, 5);
        row.querySelector(".mw-high").textContent = fmt(s.day_high, 5);
        row.querySelector(".mw-low").textContent = fmt(s.day_low, 5);
        row.querySelector(".mw-last").textContent = fmt(s.price, 5);
        const chgCell = row.querySelector(".mw-chg");
        chgCell.textContent = s.change_pct !== null && s.change_pct !== undefined ? `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%` : "—";
        chgCell.classList.add(chgClass);
        const recBadge = row.querySelector(".rec-pill");
        if (data.recommendation) {
          recBadge.textContent = data.recommendation.label;
          recBadge.classList.add(`rec-${data.recommendation.label.toLowerCase()}`);
        } else {
          recBadge.remove();
        }
      })
      .catch(() => {
        row.querySelectorAll("td").forEach((td, i) => { if (i > 0 && i < 5) td.textContent = "—"; });
        row.querySelector(".mw-chg").textContent = "no data";
        const recBadge = row.querySelector(".rec-pill");
        if (recBadge) recBadge.remove();
      });
  });

  const note = el(`<div class="name" style="margin-top:10px;">Open is today's IST-day opening rate, captured once each morning (see README) — falls back to previous close until the first capture runs.</div>`);
  box.appendChild(note);
}

document.getElementById("pairs-back-btn").addEventListener("click", showPairGroups);

// ---- pair research page ----

async function openPair(symbol) {
  const activeBtn = document.querySelector(".nav-btn.active");
  state.returnView = activeBtn ? activeBtn.dataset.view : "pairs";
  state.returnGroup = state.currentGroup || null;
  state.currentSymbol = symbol;
  showView("pair");
  const content = document.getElementById("pair-content");
  content.innerHTML = '<div class="empty">Loading…</div>';

  let data;
  try {
    data = await api(`/api/pair/${encodeURIComponent(symbol)}`);
  } catch (e) {
    content.innerHTML = `<div class="empty">Error loading ${symbol}: ${e.message}</div>`;
    return;
  }
  const s = data.snapshot;
  const ccy = s.quote_currency || "";

  const rangeLow = s["52w_low"], rangeHigh = s["52w_high"], rangePrice = s.price;
  let rangeChart = `<div class="value">${fmt(rangeLow, 5)} – ${fmt(rangeHigh, 5)}</div>`;
  if (rangeLow !== null && rangeHigh !== null && rangePrice !== null && rangeHigh > rangeLow) {
    const pct = Math.max(0, Math.min(100, ((rangePrice - rangeLow) / (rangeHigh - rangeLow)) * 100));
    rangeChart = `
      <div class="range-current">${fmt(rangePrice, 5)} <span style="color:var(--text-faint);font-weight:400;">now</span></div>
      <div class="range-track"><div class="range-fill" style="width:${pct}%"></div><div class="range-marker" style="left:${pct}%"></div></div>
      <div class="range-endlabels"><span>${fmt(rangeLow, 5)} low</span><span>${fmt(rangeHigh, 5)} high</span></div>
    `;
  }

  content.innerHTML = "";
  content.appendChild(el(`
    <div class="panel">
      <div class="row-with-avatar" style="margin-bottom:14px;">
        ${avatarHtml(s.symbol, "lg")}
        <h2 style="margin:0;font-size:16px;color:var(--text);text-transform:none;letter-spacing:0;">${s.name} (${data.pair.base}/${data.pair.quote})</h2>
      </div>
      <div class="kpi-grid">
        <div class="kpi"><div${tipAttrs("Price", "label")}>Price</div><div class="value">${fmt(s.price, 5)}</div></div>
        <div class="kpi"><div class="label">Today's Open</div><div class="value">${s.open_today !== null && s.open_today !== undefined ? fmt(s.open_today, 5) : fmt(s.prev_close, 5)}</div>${s.change_from_open_pct !== null && s.change_from_open_pct !== undefined ? `<div class="kpi-disclaimer" style="color:${s.change_from_open_pct >= 0 ? "var(--green)" : "var(--red)"};">${s.change_from_open_pct >= 0 ? "+" : ""}${s.change_from_open_pct}% since open</div>` : `<div class="kpi-disclaimer">Not captured yet today — showing prev. close</div>`}</div>
        <div class="kpi"><div${tipAttrs("Day Change %", "label")}>Day Change %</div><div class="value">${fmt(s.change_pct)}%</div></div>
        <div class="kpi"><div${tipAttrs("1-Week Change %", "label")}>1W %</div><div class="value">${fmt(s.week_change_pct)}%</div></div>
        <div class="kpi"><div${tipAttrs("1-Month Change %", "label")}>1M %</div><div class="value">${fmt(s.month_change_pct)}%</div></div>
        <div class="kpi"><div${tipAttrs("RSI (14)", "label")}>RSI14</div><div class="value">${fmt(s.rsi14, 1)}</div></div>
        <div class="kpi"><div${tipAttrs("ATR (14)", "label")}>ATR14</div><div class="value">${fmt(s.atr14, 5)} <span style="font-size:11px;color:var(--text-faint);">(${fmt(s.atr_pct)}%)</span></div></div>
        <div class="kpi range-chart"><div${tipAttrs("52-Week High", "label")}>52W Range</div>${rangeChart}</div>
      </div>
      <div class="name" style="margin-top:8px;">Quote currency: ${ccy || "—"}.</div>
    </div>
  `));

  // One chart: price with SMA20/50/200 trend overlay.
  const historyPanel = el(`
    <div class="panel">
      <h2>Price &amp; Trend (SMA20 / SMA50 / SMA200)</h2>
      <div class="period-row">
        <button class="period-btn" data-period="1mo">1M</button>
        <button class="period-btn" data-period="3mo">3M</button>
        <button class="period-btn active" data-period="6mo">6M</button>
        <button class="period-btn" data-period="1y">1Y</button>
        <button class="period-btn" data-period="2y">2Y</button>
      </div>
      <div id="price-history-chart"><div class="empty">Loading…</div></div>
    </div>
  `);
  content.appendChild(historyPanel);
  const chartBox = historyPanel.querySelector("#price-history-chart");

  async function loadIndicatorCharts(period) {
    chartBox.innerHTML = '<div class="empty">Loading…</div>';
    try {
      const points = await api(`/api/pair/${encodeURIComponent(symbol)}/indicators-history?period=${period}`);
      renderLineChart(chartBox, points, ccy, SMA_OVERLAY_SERIES);
    } catch (e) {
      chartBox.innerHTML = `<div class="empty">Could not load chart data: ${e.message}</div>`;
    }
  }
  historyPanel.querySelectorAll(".period-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      historyPanel.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadIndicatorCharts(btn.dataset.period);
    });
  });
  loadIndicatorCharts("6mo");

  const rec = data.recommendation;
  if (rec) {
    const recClass = rec.label.toLowerCase();
    const reasonItems = rec.reasoning.map((r) => `<li>${r}</li>`).join("");
    content.appendChild(el(`
      <div class="panel rec-panel rec-${recClass}">
        <div class="rec-top">
          <div class="rec-badge rec-${recClass}">${rec.label}</div>
          <div class="rec-upside">Score ${rec.score > 0 ? "+" : ""}${rec.score} / ±5</div>
        </div>
        <ul class="rec-reasoning">${reasonItems}</ul>
        <div class="rec-disclaimer">${rec.disclaimer}</div>
      </div>
    `));
  }

  const concernsPanel = el(`<div class="panel"><h2>Concern Flags</h2><div id="concerns-box"></div></div>`);
  content.appendChild(concernsPanel);
  const cbox = concernsPanel.querySelector("#concerns-box");
  if (!data.concerns.length) {
    cbox.appendChild(el('<div class="empty">No rule-based concerns flagged.</div>'));
  } else {
    data.concerns.forEach((c) => {
      cbox.appendChild(el(`<div class="concern-item"><span class="badge ${c.severity}">${c.severity}</span> ${c.message}</div>`));
    });
  }

  // Currency calendar — 2026 central-bank rate decisions for this pair's
  // base and quote currency, from the app-wide events table.
  const calPanel = el(`<div class="panel"><h2>${data.pair.base} / ${data.pair.quote} Calendar</h2><div id="pair-calendar-box"></div></div>`);
  content.appendChild(calPanel);
  const calBox = calPanel.querySelector("#pair-calendar-box");
  if (!data.calendar || !data.calendar.length) {
    calBox.appendChild(el('<div class="empty">No upcoming events for these currencies.</div>'));
  } else {
    data.calendar.slice(0, 8).forEach((e) => {
      calBox.appendChild(el(`
        <div class="event-row">
          <div class="meta">
            <span class="symbol">${e.event_date}</span> — ${e.event_type} <span class="badge">${e.currency}</span>
            <div class="name">${e.description || ""}</div>
          </div>
        </div>
      `));
    });
  }

  // Thesis
  const thesisPanel = el(`
    <div class="panel">
      <h2>Thesis & Catalysts</h2>
      <label>Thesis</label>
      <textarea id="thesis-text" placeholder="Trading thesis..."></textarea>
      <label style="margin-top:8px;display:block;">Key Risks</label>
      <textarea id="thesis-risks" placeholder="Key risks..."></textarea>
      <label style="margin-top:8px;display:block;">Catalysts</label>
      <textarea id="thesis-catalysts" placeholder="Catalysts to watch (rate decisions, data releases)..."></textarea>
      <button id="thesis-save-btn" style="margin-top:10px;">Save</button>
      <span id="thesis-saved-msg" class="name" style="margin-left:10px;"></span>
    </div>
  `);
  content.appendChild(thesisPanel);
  const thesis = await api(`/api/pair/${encodeURIComponent(symbol)}/thesis`);
  thesisPanel.querySelector("#thesis-text").value = thesis.thesis_text || "";
  thesisPanel.querySelector("#thesis-risks").value = thesis.risks || "";
  thesisPanel.querySelector("#thesis-catalysts").value = thesis.catalysts || "";
  thesisPanel.querySelector("#thesis-save-btn").addEventListener("click", async () => {
    await api(`/api/pair/${encodeURIComponent(symbol)}/thesis`, {
      method: "PUT",
      body: JSON.stringify({
        thesis_text: thesisPanel.querySelector("#thesis-text").value,
        risks: thesisPanel.querySelector("#thesis-risks").value,
        catalysts: thesisPanel.querySelector("#thesis-catalysts").value,
      }),
    });
    const msg = thesisPanel.querySelector("#thesis-saved-msg");
    msg.textContent = "Saved.";
    setTimeout(() => (msg.textContent = ""), 2000);
  });

  // Forecast tracker (target level vs actual)
  const fcPanel = el(`
    <div class="panel">
      <h2>Forecast vs Actual</h2>
      <div class="form-row">
        <input id="fc-period" type="text" placeholder="Period / date (e.g. Q1 FY26, or a specific date)">
        <input id="fc-level" type="number" step="any" placeholder="Forecast level">
        <button id="fc-add-btn">Add forecast</button>
      </div>
      <div id="fc-table" style="margin-top:12px;"></div>
    </div>
  `);
  content.appendChild(fcPanel);

  async function renderForecasts() {
    const forecasts = await api(`/api/pair/${encodeURIComponent(symbol)}/forecasts`);
    const box = fcPanel.querySelector("#fc-table");
    if (!forecasts.length) {
      box.innerHTML = '<div class="empty">No forecasts logged yet.</div>';
      return;
    }
    let rows = forecasts.map((f) => {
      const varPct = f.est_level && f.actual_level ? (((f.actual_level - f.est_level) / Math.abs(f.est_level)) * 100).toFixed(2) + "%" : "—";
      return `
        <tr>
          <td>${f.period_label}</td>
          <td>${fmt(f.est_level, 5)}</td>
          <td><input type="number" step="any" class="actual-level-input" data-id="${f.id}" value="${f.actual_level ?? ""}" style="width:100px;"></td>
          <td>${varPct}</td>
        </tr>
      `;
    }).join("");
    box.innerHTML = `
      <table>
        <thead><tr><th>Period</th><th>Forecast</th><th>Actual</th><th>Var %</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    box.querySelectorAll(".actual-level-input").forEach((inp) => {
      inp.addEventListener("change", async () => {
        await api(`/api/forecasts/${inp.dataset.id}/actual`, {
          method: "PUT",
          body: JSON.stringify({ actual_level: inp.value === "" ? null : parseFloat(inp.value) }),
        });
        renderForecasts();
      });
    });
  }
  await renderForecasts();

  fcPanel.querySelector("#fc-add-btn").addEventListener("click", async () => {
    const period = fcPanel.querySelector("#fc-period").value.trim();
    if (!period) return;
    const level = fcPanel.querySelector("#fc-level").value;
    await api(`/api/pair/${encodeURIComponent(symbol)}/forecasts`, {
      method: "POST",
      body: JSON.stringify({ period_label: period, est_level: level === "" ? null : parseFloat(level) }),
    });
    fcPanel.querySelector("#fc-period").value = "";
    fcPanel.querySelector("#fc-level").value = "";
    renderForecasts();
  });

  // Notes
  const notesPanel = el(`
    <div class="panel">
      <h2>Research Notes</h2>
      <textarea id="note-input" placeholder="Add a note..."></textarea>
      <button id="note-add-btn" style="margin-top:8px;">Add note</button>
      <div id="notes-list" style="margin-top:14px;"></div>
    </div>
  `);
  content.appendChild(notesPanel);

  async function renderNotes() {
    const notes = await api(`/api/pair/${encodeURIComponent(symbol)}/notes`);
    const box = notesPanel.querySelector("#notes-list");
    if (!notes.length) {
      box.innerHTML = '<div class="empty">No notes yet.</div>';
      return;
    }
    box.innerHTML = "";
    notes.forEach((n) => {
      box.appendChild(el(`
        <div class="note-item">
          <div class="note-time">${new Date(n.created_at).toLocaleString()}</div>
          <div>${n.body.replace(/</g, "&lt;")}</div>
        </div>
      `));
    });
  }
  await renderNotes();

  notesPanel.querySelector("#note-add-btn").addEventListener("click", async () => {
    const input = notesPanel.querySelector("#note-input");
    const body = input.value.trim();
    if (!body) return;
    await api(`/api/pair/${encodeURIComponent(symbol)}/notes`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
    input.value = "";
    renderNotes();
  });
}

// ---- calendar view ----

// Every currency that appears as a base or quote across the tracked
// universe — used for both the "filter by currency" select and the
// "tag a new event to a currency" select.
const TRACKED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "INR"];

function populateCurrencySelects() {
  const filterHtml = '<option value="">All currencies</option>' + TRACKED_CURRENCIES.map((c) => `<option value="${c}">${c}</option>`).join("");
  const tagHtml = '<option value="">No specific currency</option>' + TRACKED_CURRENCIES.map((c) => `<option value="${c}">${c}</option>`).join("");
  document.getElementById("calendar-currency-filter").innerHTML = filterHtml;
  document.getElementById("event-currency").innerHTML = tagHtml;
}

async function populateEventPairSelect() {
  const select = document.getElementById("event-symbol");
  const pairs = await getPairs();
  select.innerHTML = '<option value="">No specific pair</option>' + pairs.map((p) => `<option value="${p.symbol}">${p.base}/${p.quote}</option>`).join("");
}

async function loadCalendar() {
  const box = document.getElementById("calendar-list");
  box.innerHTML = '<div class="empty">Loading…</div>';
  const events = await api("/api/events");
  const currencyFilter = document.getElementById("calendar-currency-filter").value;
  const filtered = currencyFilter ? events.filter((e) => e.currency === currencyFilter) : events;
  if (!filtered.length) {
    box.innerHTML = '<div class="empty">No events for this filter.</div>';
    return;
  }
  const today = new Date().toISOString().slice(0, 10);
  box.innerHTML = "";
  filtered.forEach((e) => {
    const overdue = e.event_date < today;
    const tag = e.currency ? `<span class="badge">${e.currency}</span>` : e.symbol ? `<span class="badge">${e.symbol.replace("=X", "")}</span>` : "";
    box.appendChild(el(`
      <div class="event-row">
        <div class="meta">
          <span class="symbol">${e.event_date}</span> — ${e.event_type} ${tag}
          <div class="name">${e.description || ""}</div>
        </div>
        <span class="badge ${overdue ? "" : "low"}">${overdue ? "past" : "upcoming"}</span>
      </div>
    `));
  });
}

document.getElementById("calendar-currency-filter").addEventListener("change", loadCalendar);

document.getElementById("event-add-btn").addEventListener("click", async () => {
  const symbol = document.getElementById("event-symbol").value;
  const currency = document.getElementById("event-currency").value;
  const type = document.getElementById("event-type").value.trim();
  const date = document.getElementById("event-date").value;
  const desc = document.getElementById("event-desc").value.trim();
  if (!type || !date) return;
  await api("/api/events", {
    method: "POST",
    body: JSON.stringify({ symbol: symbol || null, currency: currency || null, event_type: type, event_date: date, description: desc || null }),
  });
  document.getElementById("event-symbol").value = "";
  document.getElementById("event-currency").value = "";
  document.getElementById("event-type").value = "";
  document.getElementById("event-date").value = "";
  document.getElementById("event-desc").value = "";
  loadCalendar();
});

// ---- wiring ----

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const view = btn.dataset.view;
    showView(view);
    if (view === "pairs") showPairGroups();
    if (view === "calendar") loadCalendar();
  });
});

document.getElementById("back-btn").addEventListener("click", () => {
  const view = state.returnView || "pairs";
  showView(view);
  if (view === "calendar") loadCalendar();
  else if (state.returnGroup) loadGroupTable(state.returnGroup);
  else showPairGroups();
});

showPairGroups();
populateCurrencySelects();
populateEventPairSelect();
