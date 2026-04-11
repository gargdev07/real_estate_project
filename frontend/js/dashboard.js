/* ──────────────────────────────────────────────────────────────
   Dashboard JS — all chart rendering + filter + polling logic
   ────────────────────────────────────────────────────────────── */

const REFRESH_INTERVAL_MS = 30_000;
let charts = {};
let refreshTimer = null;
let currentCity = '';

// Chart.js color palette
const CITY_COLORS = {
  'Gurgaon':   { border: '#4F46E5', bg: 'rgba(79,70,229,0.12)' },
  'Hyderabad': { border: '#059669', bg: 'rgba(5,150,105,0.12)'  },
  'Kolkata':   { border: '#D97706', bg: 'rgba(217,119,6,0.12)'  },
  'Mumbai':    { border: '#DC2626', bg: 'rgba(220,38,38,0.12)'  },
};
const PROP_COLORS = ['#4F46E5','#059669','#D97706','#DC2626','#7C3AED','#0891B2','#DB2777'];

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  if (!requireAuth()) return;

  const user = await API.me().catch(() => null);
  if (user) {
    document.getElementById('navUsername').textContent = user.username;
    document.getElementById('navRole').textContent = user.role;
    document.getElementById('navAvatar').textContent = user.username[0].toUpperCase();
  }

  const cities = await API.getCities().catch(() => []);
  const citySelect = document.getElementById('cityFilter');
  cities.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.city_name;
    opt.textContent = c.city_name;
    citySelect.appendChild(opt);
  });

  await loadAll();
  startAutoRefresh();
}

async function loadAll() {
  setRefreshing(true);
  // Run all loaders independently — one failure won't kill the others
  await Promise.allSettled([
    loadSummary().catch(e => console.warn('summary:', e)),
    loadPriceTrends().catch(e => console.warn('price-trends:', e)),
    loadLocalityDemand().catch(e => console.warn('locality-demand:', e)),
    loadPropertyDist().catch(e => console.warn('prop-dist:', e)),
    loadBedroomPrice().catch(e => console.warn('bedroom-price:', e)),
    loadAgentTable().catch(e => console.warn('agent-table:', e)),
  ]);
  document.getElementById('lastUpdated').textContent =
    'Updated ' + new Date().toLocaleTimeString('en-IN');
  setRefreshing(false);
}

function setRefreshing(v) {
  document.getElementById('refreshIcon').classList.toggle('refreshing', v);
}

function startAutoRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(loadAll, REFRESH_INTERVAL_MS);
}

// ── Filters ───────────────────────────────────────────────────────────────────
function onCityChange() {
  currentCity = document.getElementById('cityFilter').value;
  loadAll();
}

function onDateChange() { loadPriceTrends(); }

// ── KPI Summary ──────────────────────────────────────────────────────────────
async function loadSummary() {
  const s = await API.getSummary();
  document.getElementById('kpiTotalListings').textContent    = Fmt.number(s.total_listings);
  document.getElementById('kpiActiveListings').textContent   = Fmt.number(s.active_listings);
  document.getElementById('kpiTransactions').textContent     = Fmt.number(s.total_transactions);
  document.getElementById('kpiSalesValue').textContent       = Fmt.price(s.total_sales_value);
  document.getElementById('kpiAvgPrice').textContent         = Fmt.price(s.avg_price_inr);
  document.getElementById('kpiAvgPriceSqft').textContent     = s.avg_price_sqft ? '₹' + Fmt.number(s.avg_price_sqft) + '/sqft' : '—';
  document.getElementById('kpiCities').textContent           = s.cities_covered;
  document.getElementById('kpiLocalities').textContent       = s.localities_covered + ' localities';
}

// ── Chart 1: Price Trends Line Chart ─────────────────────────────────────────
async function loadPriceTrends() {
  const params = { city_name: currentCity };
  const df = document.getElementById('dateFrom').value;
  const dt = document.getElementById('dateTo').value;
  if (df) params.date_from = df;
  if (dt) params.date_to   = dt;

  const data = await API.getPriceTrends(params);
  if (!data || !data.length) return;

  // Group by city
  const cityMap = {};
  data.forEach(r => {
    if (!cityMap[r.city_name]) cityMap[r.city_name] = {};
    cityMap[r.city_name][r.month] = parseFloat(r.avg_price_sqft || 0);
  });

  const allMonths = [...new Set(data.map(r => r.month))].sort();
  const datasets = Object.entries(cityMap).map(([city, monthMap]) => ({
    label: city,
    data: allMonths.map(m => monthMap[m] || null),
    borderColor:     (CITY_COLORS[city] || { border: '#888' }).border,
    backgroundColor: (CITY_COLORS[city] || { bg: 'transparent' }).bg,
    borderWidth: 2.5,
    pointRadius: 3,
    tension: 0.35,
    spanGaps: true,
    fill: false,
  }));

  renderOrUpdate('chartPriceTrends', 'line', {
    labels: allMonths,
    datasets,
  }, {
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { position: 'top', labels: { boxWidth: 12, font: { size: 12 } } },
      tooltip: {
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ₹${Fmt.number(ctx.raw)}/sqft`,
        },
      },
    },
    scales: {
      x: { grid: { color: 'rgba(128,128,128,0.1)' }, ticks: { font: { size: 11 } } },
      y: {
        grid: { color: 'rgba(128,128,128,0.1)' },
        ticks: { font: { size: 11 }, callback: v => '₹' + Fmt.number(v) },
      },
    },
  });
}

// ── Chart 2: Locality Demand Bar Chart ───────────────────────────────────────
async function loadLocalityDemand() {
  const data = await API.getLocalityDemand({ city_name: currentCity, top_n: 15 });
  if (!data || !data.length) return;

  // Aggregate by locality (sum listing_count across property types)
  const agg = {};
  data.forEach(r => {
    if (!agg[r.locality_name]) agg[r.locality_name] = { count: 0, priceSum: 0, n: 0 };
    agg[r.locality_name].count += r.listing_count;
    if (r.avg_price_sqft) { agg[r.locality_name].priceSum += parseFloat(r.avg_price_sqft); agg[r.locality_name].n++; }
  });

  const sorted = Object.entries(agg)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 15);

  const labels   = sorted.map(([loc]) => loc.length > 22 ? loc.slice(0, 22) + '…' : loc);
  const counts   = sorted.map(([, v]) => v.count);
  const avgPrices= sorted.map(([, v]) => v.n ? Math.round(v.priceSum / v.n) : 0);

  renderOrUpdate('chartLocalityDemand', 'bar', {
    labels,
    datasets: [
      {
        label: 'Listings',
        data: counts,
        backgroundColor: 'rgba(79,70,229,0.8)',
        borderRadius: 4,
        yAxisID: 'y',
      },
      {
        label: 'Avg ₹/sqft',
        data: avgPrices,
        type: 'line',
        borderColor: '#D97706',
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.3,
        yAxisID: 'y2',
      },
    ],
  }, {
    plugins: {
      legend: { position: 'top', labels: { boxWidth: 12, font: { size: 12 } } },
      tooltip: {
        callbacks: {
          label: ctx => ctx.datasetIndex === 0
            ? ` ${ctx.raw} listings`
            : ` ₹${Fmt.number(ctx.raw)}/sqft`,
        },
      },
    },
    scales: {
      x: { ticks: { font: { size: 10 }, maxRotation: 40 }, grid: { display: false } },
      y:  { position: 'left',  grid: { color: 'rgba(128,128,128,0.1)' }, ticks: { font:{size:11} } },
      y2: { position: 'right', grid: { display: false }, ticks: { font:{size:11}, callback: v => '₹'+Fmt.number(v) } },
    },
  });
}

// ── Chart 3: Property Type Donut ─────────────────────────────────────────────
async function loadPropertyDist() {
  const data = await API.getPropertyDist({ city_name: currentCity });
  if (!data || !data.length) return;

  // Aggregate by property_type
  const agg = {};
  data.forEach(r => {
    const key = r.property_type || 'Unknown';
    if (!agg[key]) agg[key] = { count: 0, priceSum: 0, n: 0 };
    agg[key].count += r.listing_count;
    if (r.avg_price_sqft) { agg[key].priceSum += parseFloat(r.avg_price_sqft); agg[key].n++; }
  });

  const entries = Object.entries(agg).sort((a, b) => b[1].count - a[1].count);
  const labels  = entries.map(([k]) => k);
  const counts  = entries.map(([,v]) => v.count);
  const total   = counts.reduce((a,b) => a+b, 0);

  renderOrUpdate('chartPropDist', 'doughnut', {
    labels,
    datasets: [{
      data: counts,
      backgroundColor: PROP_COLORS.slice(0, labels.length),
      borderWidth: 2,
      borderColor: 'transparent',
      hoverOffset: 8,
    }],
  }, {
    cutout: '62%',
    plugins: {
      legend: { position: 'right', labels: { boxWidth: 12, font: { size: 12 }, padding: 14 } },
      tooltip: {
        callbacks: {
          label: ctx => ` ${ctx.label}: ${ctx.raw} (${((ctx.raw/total)*100).toFixed(1)}%)`,
        },
      },
    },
  });

  // Populate prop type KPI cards below the donut
  const breakdown = document.getElementById('propBreakdown');
  if (breakdown) {
    breakdown.innerHTML = entries.slice(0, 4).map(([k, v], i) => `
      <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);">
        <span style="width:10px;height:10px;border-radius:50%;background:${PROP_COLORS[i]};flex-shrink:0"></span>
        <span style="flex:1;font-size:12px;color:var(--text)">${k}</span>
        <span style="font-size:12px;font-weight:600;color:var(--text)">${Fmt.number(v.count)}</span>
        <span style="font-size:11px;color:var(--muted);min-width:70px;text-align:right">
          ${v.n ? '₹'+Fmt.number(v.priceSum/v.n)+'/sqft' : '—'}
        </span>
      </div>
    `).join('');
  }
}

// ── Chart 4: Bedroom vs Price Bar Chart ──────────────────────────────────────
async function loadBedroomPrice() {
  const data = await API.getBedroomPrice({ city_name: currentCity });
  if (!data || !data.length) return;

  const cityMap = {};
  data.forEach(r => {
    if (!cityMap[r.city_name]) cityMap[r.city_name] = {};
    cityMap[r.city_name][r.bedroom_num] = parseFloat(r.avg_price_sqft || 0);
  });

  const bedrooms  = [1, 2, 3, 4, 5, 6];
  const datasets  = Object.entries(cityMap).map(([city, bm], i) => ({
    label: city,
    data: bedrooms.map(b => bm[b] || null),
    backgroundColor: Object.values(CITY_COLORS)[i]?.border || PROP_COLORS[i],
    borderRadius: 4,
  }));

  renderOrUpdate('chartBedroomPrice', 'bar', {
    labels: bedrooms.map(b => b + ' BHK'),
    datasets,
  }, {
    plugins: {
      legend: { position: 'top', labels: { boxWidth: 12, font: { size: 12 } } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ₹${Fmt.number(ctx.raw)}/sqft` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 12 } } },
      y: { grid: { color: 'rgba(128,128,128,0.1)' }, ticks: { callback: v => '₹'+Fmt.number(v), font:{size:11} } },
    },
  });
}

// ── Agent Performance Table ───────────────────────────────────────────────────
async function loadAgentTable() {
  const data = await API.getAgentPerf({ city_name: currentCity, top_n: 10 });
  const tbody = document.getElementById('agentTableBody');
  if (!tbody || !data) return;

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No data</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map((a, i) => `
    <tr>
      <td><span style="font-weight:600;color:var(--accent)">#${i+1}</span></td>
      <td>
        <div style="font-weight:500">${a.contact_name || '—'}</div>
        <div style="font-size:11px;color:var(--muted)">${a.company_name || ''}</div>
      </td>
      <td>${a.city_name || '—'}</td>
      <td style="text-align:right">${Fmt.number(a.total_listings)}</td>
      <td style="text-align:right;font-weight:600;color:var(--green)">${Fmt.price(a.total_sales_value)}</td>
    </tr>
  `).join('');
}

// ── Chart helper — create or update ─────────────────────────────────────────
function renderOrUpdate(canvasId, type, chartData, options = {}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const defaults = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: true } },
  };
  const merged = deepMerge(defaults, options);

  if (charts[canvasId]) {
    charts[canvasId].data = chartData;
    charts[canvasId].options = merged;
    charts[canvasId].update('active');
  } else {
    charts[canvasId] = new Chart(canvas.getContext('2d'), {
      type,
      data: chartData,
      options: merged,
    });
  }
}

function deepMerge(a, b) {
  const result = { ...a };
  for (const [k, v] of Object.entries(b)) {
    result[k] = (v && typeof v === 'object' && !Array.isArray(v) && a[k])
      ? deepMerge(a[k], v) : v;
  }
  return result;
}

// ── Logout ────────────────────────────────────────────────────────────────────
function logout() {
  clearInterval(refreshTimer);
  localStorage.removeItem('re_token');
  window.location.href = 'login.html';
}

// ── Manual refresh button ────────────────────────────────────────────────────
async function manualRefresh() {
  clearInterval(refreshTimer);
  await loadAll();
  startAutoRefresh();
}

window.addEventListener('DOMContentLoaded', init);
