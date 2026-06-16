import json
from flask import Blueprint, jsonify, request, render_template_string
import db

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

ANALYTICS_HTML = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Аналитика парковок</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      background:#1a1a2e; color:#eee;
      font-family:'Segoe UI',sans-serif;
      min-height:100vh; padding:24px;
      display:flex; flex-direction:column; align-items:center; gap:20px;
    }

    .topbar {
      width:100%; max-width:1000px;
      display:flex; align-items:center; gap:14px; flex-wrap:wrap;
    }
    h1 { font-size:20px; color:#00d4ff; flex:1; }
    .btn {
      padding:7px 18px; border-radius:6px; border:none;
      font-size:13px; cursor:pointer; font-weight:600; transition:opacity .15s;
    }
    .btn:hover { opacity:.82; }
    .btn-back    { background:#2a2a4a; color:#aaa; border:1px solid #444; }
    .btn-period  { background:#2a2a4a; color:#888; border:1px solid #333; }
    .btn-period.active { background:#00d4ff22; color:#00d4ff; border-color:#00d4ff66; }

    .controls {
      width:100%; max-width:1000px;
      display:flex; align-items:center; gap:12px; flex-wrap:wrap;
    }
    select {
      background:#2a2a4a; color:#eee;
      border:1px solid #00d4ff44; border-radius:6px;
      padding:7px 14px; font-size:14px;
    }
    .periods { display:flex; gap:6px; }

    /* Сводка */
    .summary {
      width:100%; max-width:1000px;
      display:grid; grid-template-columns:repeat(4,1fr); gap:12px;
    }
    .card {
      background:#1e1e3a; border:1px solid #2a2a4a;
      border-radius:10px; padding:16px; text-align:center;
    }
    .card .val { font-size:28px; font-weight:700; margin-bottom:4px; }
    .card .lbl { font-size:12px; color:#666; }
    .c-blue  .val { color:#00d4ff; }
    .c-green .val { color:#00ff88; }
    .c-red   .val { color:#ff4444; }
    .c-amber .val { color:#ffaa00; }

    /* Графики */
    .chart-card {
      width:100%; max-width:1000px;
      background:#1e1e3a; border:1px solid #2a2a4a;
      border-radius:12px; padding:20px;
    }
    .chart-card h2 {
      font-size:14px; color:#aaa; margin-bottom:16px;
    }
    .chart-wrap { position:relative; height:220px; }

    /* Пиковые часы */
    .peak-wrap { position:relative; height:180px; }

    .no-data {
      text-align:center; padding:40px;
      color:#444; font-size:14px;
    }
  </style>
</head>
<body>

<div class="topbar">
  <h1>📊 Аналитика парковок</h1>
  <a href="/"><button class="btn btn-back" type="button">← Мониторинг</button></a>
  <a href="/map"><button class="btn btn-back" type="button">🗺 Карта</button></a>
</div>

<!-- Управление -->
<div class="controls">
  <select id="selParking" onchange="load()">
    <option value="">— выберите парковку —</option>
  </select>
  <div class="periods">
    <button class="btn btn-period active" data-p="hour"  onclick="setPeriod('hour')">1 час</button>
    <button class="btn btn-period"        data-p="day"   onclick="setPeriod('day')">24 часа</button>
    <button class="btn btn-period"        data-p="week"  onclick="setPeriod('week')">7 дней</button>
    <button class="btn btn-period"        data-p="month" onclick="setPeriod('month')">30 дней</button>
  </div>
</div>

<!-- Сводные карточки -->
<div class="summary" id="summary" style="display:none">
  <div class="card c-blue">
    <div class="val" id="sAvg">—</div>
    <div class="lbl">Средняя загруженность</div>
  </div>
  <div class="card c-red">
    <div class="val" id="sMax">—</div>
    <div class="lbl">Максимум за сутки</div>
  </div>
  <div class="card c-green">
    <div class="val" id="sMin">—</div>
    <div class="lbl">Минимум за сутки</div>
  </div>
  <div class="card c-amber">
    <div class="val" id="sRec">—</div>
    <div class="lbl">Записей в БД</div>
  </div>
</div>

<!-- График загруженности -->
<div class="chart-card" id="chartCard" style="display:none">
  <h2>📈 Загруженность по времени</h2>
  <div class="chart-wrap">
    <canvas id="lineChart"></canvas>
  </div>
</div>

<!-- Пиковые часы -->
<div class="chart-card" id="peakCard" style="display:none">
  <h2>🕐 Средняя загруженность по часам суток</h2>
  <div class="peak-wrap">
    <canvas id="barChart"></canvas>
  </div>
</div>

<div class="no-data" id="noData" style="display:none">
  Нет данных за выбранный период. Запустите мониторинг — данные начнут накапливаться.
</div>

<script>
let period   = 'hour';
let lineChart = null;
let barChart  = null;

// ── Инициализация графиков ─────────────────────────────────────────────────
function initLineChart() {
  const ctx = document.getElementById('lineChart').getContext('2d');
  lineChart = new Chart(ctx, {
    type: 'line',
    data: { labels:[], datasets:[
      { label:'Занято %', data:[], borderColor:'#ff4444',
        backgroundColor:'rgba(255,68,68,0.08)', fill:true,
        tension:0.3, pointRadius:0, borderWidth:2 },
      { label:'Свободно %', data:[], borderColor:'#00ff88',
        backgroundColor:'rgba(0,255,136,0.06)', fill:true,
        tension:0.3, pointRadius:0, borderWidth:2 }
    ]},
    options: {
      animation:false, responsive:true, maintainAspectRatio:false,
      scales:{
        x:{ ticks:{color:'#555', maxTicksLimit:10, font:{size:11}}, grid:{color:'#222'} },
        y:{ min:0, max:100,
            ticks:{color:'#555', callback:v=>v+'%', font:{size:11}},
            grid:{color:'#222'} }
      },
      plugins:{ legend:{ labels:{color:'#888', font:{size:12}} } }
    }
  });
}

function initBarChart() {
  const ctx = document.getElementById('barChart').getContext('2d');
  barChart = new Chart(ctx, {
    type: 'bar',
    data: { labels:[], datasets:[{
      label:'Средняя загруженность %',
      data:[],
      backgroundColor: ctx => {
        const v = ctx.raw;
        return v >= 80 ? '#ff444488' : v >= 50 ? '#ffaa0088' : '#00cc6688';
      },
      borderColor: ctx => {
        const v = ctx.raw;
        return v >= 80 ? '#ff4444' : v >= 50 ? '#ffaa00' : '#00cc66';
      },
      borderWidth:1, borderRadius:4
    }]},
    options:{
      animation:false, responsive:true, maintainAspectRatio:false,
      scales:{
        x:{ ticks:{color:'#555', font:{size:11}}, grid:{color:'#222'} },
        y:{ min:0, max:100,
            ticks:{color:'#555', callback:v=>v+'%', font:{size:11}},
            grid:{color:'#222'} }
      },
      plugins:{ legend:{display:false} }
    }
  });
}

// ── Загрузка данных ────────────────────────────────────────────────────────
async function load() {
  const label = document.getElementById('selParking').value;
  if (!label) return;

  const [statsRes, peakRes, sumRes] = await Promise.all([
    fetch(`/analytics/stats/${encodeURIComponent(label)}?period=${period}`),
    fetch(`/analytics/peak_hours/${encodeURIComponent(label)}`),
    fetch(`/analytics/summary/${encodeURIComponent(label)}`)
  ]);

  const stats   = await statsRes.json();
  const peaks   = await peakRes.json();
  const summary = await sumRes.json();

  const hasData = stats.length > 0;
  document.getElementById('noData').style.display    = hasData ? 'none' : 'block';
  document.getElementById('chartCard').style.display = hasData ? 'block' : 'none';
  document.getElementById('peakCard').style.display  = peaks.length ? 'block' : 'none';
  document.getElementById('summary').style.display   = hasData ? 'grid' : 'none';

  if (hasData) updateLineChart(stats);
  if (peaks.length) updateBarChart(peaks);
  if (summary) updateSummary(summary);
}

function updateLineChart(stats) {
  if (!lineChart) initLineChart();
  const labels = stats.map(s => {
    const d = new Date(s.ts.replace(' ','T'));
    return period === 'hour'
      ? d.toLocaleTimeString('ru', {hour:'2-digit', minute:'2-digit', second:'2-digit'})
      : period === 'day'
      ? d.toLocaleTimeString('ru', {hour:'2-digit', minute:'2-digit'})
      : d.toLocaleDateString('ru', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
  });
  lineChart.data.labels                   = labels;
  lineChart.data.datasets[0].data         = stats.map(s => s.pct);
  lineChart.data.datasets[1].data         = stats.map(s => 100 - s.pct);
  lineChart.update();
}

function updateBarChart(peaks) {
  if (!barChart) initBarChart();
  // Заполняем все 24 часа, даже если данных нет
  const hourMap = {};
  peaks.forEach(p => { hourMap[p.hour] = p.avg_pct; });
  const labels = Array.from({length:24}, (_,i) => i.toString().padStart(2,'0')+':00');
  const data   = Array.from({length:24}, (_,i) => hourMap[i] ?? null);
  barChart.data.labels         = labels;
  barChart.data.datasets[0].data = data;
  barChart.update();
}

function updateSummary(s) {
  document.getElementById('sAvg').textContent = (s.avg_pct ?? '—') + (s.avg_pct != null ? '%' : '');
  document.getElementById('sMax').textContent = (s.max_pct ?? '—') + (s.max_pct != null ? '%' : '');
  document.getElementById('sMin').textContent = (s.min_pct ?? '—') + (s.min_pct != null ? '%' : '');
  document.getElementById('sRec').textContent = s.records ?? '—';
}

// ── Период ────────────────────────────────────────────────────────────────
function setPeriod(p) {
  period = p;
  document.querySelectorAll('.btn-period').forEach(b => {
    b.classList.toggle('active', b.dataset.p === p);
  });
  load();
}

// ── Список парковок ───────────────────────────────────────────────────────
async function loadParkingList() {
  const res  = await fetch('/analytics/parkings');
  const list = await res.json();
  const sel  = document.getElementById('selParking');
  list.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.label;
    opt.textContent = p.name || p.label;
    sel.appendChild(opt);
  });
  if (list.length === 1) { sel.value = list[0].label; load(); }
}

loadParkingList();
</script>
</body>
</html>
"""


@analytics_bp.route('/')
def analytics_page():
    return render_template_string(ANALYTICS_HTML)


@analytics_bp.route('/parkings')
def parkings():
    return jsonify(db.get_all_parkings())


@analytics_bp.route('/stats/<label>')
def stats(label):
    period = request.args.get('period', 'day')
    return jsonify(db.get_stats(label, period))


@analytics_bp.route('/peak_hours/<label>')
def peak_hours(label):
    return jsonify(db.get_peak_hours(label))


@analytics_bp.route('/summary/<label>')
def summary(label):
    return jsonify(db.get_summary(label))
