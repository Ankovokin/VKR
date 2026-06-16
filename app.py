import os
import json
import csv
import io
import time
from collections import deque
from datetime import datetime
import cv2
import numpy as np
import tensorflow as tf
from flask import Flask, Response, render_template_string, jsonify, request
from editor_blueprint import editor_bp
from map_blueprint import map_bp
from analytics_blueprint import analytics_bp
import db

app = Flask(__name__)
app.register_blueprint(editor_bp)
app.register_blueprint(map_bp)
app.register_blueprint(analytics_bp)

# Инициализируем БД при старте (создаёт таблицы, мигрирует locations.json)
db.init_db()

# ── Модель ─────────────────────────────────────────────────────────────────
classifier = tf.keras.models.load_model("models/parking_classifier.h5")

# ── Глобальное состояние ───────────────────────────────────────────────────
latest_stats  = {"free": 0, "occupied": 0, "total": 0, "pct": 0}
current_video = "vid_frags/video_testM.mp4"
current_spots = "spots/spotsM.txt"
current_threshold = 0.5          # меняется слайдером без перезапуска

# История для графика и CSV: deque последних 300 точек (5 мин при 1 сек)
stats_history = deque(maxlen=300)

UPLOAD_FOLDER = "vid_frags"
SPOTS_FOLDER  = "spots"


# ── Утилиты ────────────────────────────────────────────────────────────────
def load_spots(file_path):
    spots = []
    if not os.path.exists(file_path):
        return spots
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                x1, y1, x2, y2 = map(int, line.split(","))
                spots.append((x1, y1, x2, y2))
            except ValueError:
                continue
    return spots


def get_available_parkings():
    result = []
    if not os.path.exists(UPLOAD_FOLDER):
        return result
    for fname in sorted(os.listdir(UPLOAD_FOLDER)):
        if not fname.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            continue
        spots_name = os.path.splitext(fname)[0] + '.txt'
        spots_path = os.path.join(SPOTS_FOLDER, spots_name)
        if os.path.exists(spots_path):
            result.append({
                "label": os.path.splitext(fname)[0],
                "video": os.path.join(UPLOAD_FOLDER, fname),
                "spots": spots_path
            })
    return result


# ── Генератор кадров ───────────────────────────────────────────────────────
def generate_frames(video_path, spots_file):
    global latest_stats, stats_history
    spots = load_spots(spots_file)
    cap   = cv2.VideoCapture(video_path)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        if not spots:
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                   + buffer.tobytes() + b'\r\n')
            continue

        # Используем current_threshold — подхватывает изменения слайдера
        threshold = current_threshold

        patches = []
        for (x1, y1, x2, y2) in spots:
            patch = frame[y1:y2, x1:x2]
            if patch.size == 0:
                patches.append(np.zeros((64, 64, 3)))
                continue
            patch = cv2.resize(patch, (64, 64)) / 255.0
            patches.append(patch)

        preds = classifier.predict(np.array(patches), verbose=0)

        free, occupied = 0, 0
        for i, (x1, y1, x2, y2) in enumerate(spots):
            is_occupied = preds[i][0] >= threshold
            if is_occupied:
                occupied += 1
                color = (0, 0, 255)
            else:
                free += 1
                color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, str(i + 1), (x1 + 2, y1 + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        total = free + occupied
        pct   = round(occupied / total * 100) if total > 0 else 0

        latest_stats = {"free": free, "occupied": occupied,
                        "total": total, "pct": pct}

        # Пишем в историю для графика и CSV (in-memory, для текущей сессии)
        stats_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "free": free,
            "occupied": occupied,
            "pct": pct
        })

        # Пишем в БД (постоянное хранилище)
        parking_label = os.path.splitext(os.path.basename(current_video))[0]
        try:
            db.add_stat(parking_label, free, occupied, total, pct)
            db.update_total_spots(parking_label, total)
        except Exception:
            pass  # БД не должна ронять видеопоток

        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
               + buffer.tobytes() + b'\r\n')

    cap.release()


# ── HTML ───────────────────────────────────────────────────────────────────
INDEX_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Парковка — мониторинг</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      background:#1a1a2e; color:#eee;
      font-family:'Segoe UI',sans-serif;
      display:flex; flex-direction:column;
      align-items:center; padding:30px; gap:18px;
    }
    h1 { font-size:24px; color:#00d4ff; letter-spacing:1px; }

    .top-bar {
      display:flex; gap:12px; align-items:center;
      flex-wrap:wrap; justify-content:center;
    }
    select {
      background:#2a2a4a; color:#eee;
      border:1px solid #00d4ff55;
      padding:8px 14px; border-radius:6px; font-size:14px;
    }
    .btn {
      padding:8px 20px; border-radius:6px; border:none;
      font-size:14px; cursor:pointer; font-weight:600;
      transition:opacity .15s;
    }
    .btn:hover    { opacity:.85; }
    .btn-primary  { background:#00d4ff; color:#111; }
    .btn-editor   { background:#9b59b6; color:#fff; }
    .btn-map      { background:#2980b9; color:#fff; }
    .btn-analytics{ background:#8e44ad; color:#fff; }
    .btn-csv      { background:#27ae60; color:#fff; }

    .video-container {
      border:2px solid #00d4ff33; border-radius:12px;
      overflow:hidden; box-shadow:0 0 30px #00d4ff22;
    }
    img { display:block; max-width:900px; width:100%; }

    /* ── Статусные бейджи ── */
    .status { display:flex; gap:16px; flex-wrap:wrap; justify-content:center; }
    .badge {
      padding:10px 24px; border-radius:8px;
      font-size:16px; font-weight:bold;
      min-width:180px; text-align:center;
    }
    .free     { background:#1a472a; color:#00ff88; border:1px solid #00ff88; }
    .occupied { background:#4a1a1a; color:#ff4444; border:1px solid #ff4444; }
    .percent  { background:#1a2a47; color:#00d4ff; border:1px solid #00d4ff; }

    /* ── Слайдер порога ── */
    .threshold-row {
      display:flex; align-items:center; gap:14px;
      background:#1e1e3a; padding:12px 24px;
      border-radius:10px; border:1px solid #333;
    }
    .threshold-row label { font-size:14px; color:#aaa; }
    input[type=range] {
      width:180px; accent-color:#00d4ff; cursor:pointer;
    }
    #threshVal {
      font-size:15px; font-weight:700;
      color:#00d4ff; min-width:36px; text-align:center;
    }

    /* ── График ── */
    .chart-wrap {
      background:#1e1e3a; border-radius:12px;
      border:1px solid #2a2a4a; padding:20px;
      width:100%; max-width:900px;
    }
    .chart-wrap h2 {
      font-size:15px; color:#aaa;
      margin-bottom:12px; text-align:center;
    }
    canvas#chart { width:100% !important; height:220px !important; }

    .no-spots {
      background:#2a2a1a; border:1px solid #ffaa00;
      color:#ffaa00; padding:12px 24px;
      border-radius:8px; font-size:14px; display:none;
    }
  </style>
</head>
<body>
  <h1>🅿 Мониторинг парковки</h1>

  <!-- Верхняя панель -->
  <div class="top-bar">
    <select id="parkingSelect" onchange="changeParking()">
      <option value="">— выберите парковку —</option>
    </select>
    <button class="btn btn-primary"  onclick="reloadFeed()">▶ Запустить</button>
    <a href="/editor"><button class="btn btn-editor" type="button">✏️ Редактор</button></a>
    <a href="/map"><button class="btn btn-map" type="button">🗺 Карта</button></a>
    <a href="/analytics"><button class="btn btn-analytics" type="button">📊 Аналитика</button></a>
    <button class="btn btn-csv"      onclick="exportCSV()">⬇ CSV</button>
  </div>

  <div class="no-spots" id="noSpots">
    ⚠ Для этого видео нет разметки.
    <a href="/editor" style="color:#ffaa00">Перейдите в редактор</a>.
  </div>

  <!-- Видео -->
  <div class="video-container">
    <img id="feed" src="/video_feed" alt="Видеопоток">
  </div>

  <!-- Статистика -->
  <div class="status">
    <div class="badge free">🟢 Свободно: <span id="free">—</span></div>
    <div class="badge occupied">🔴 Занято: <span id="occupied">—</span></div>
    <div class="badge percent">📊 Занято: <span id="pct">—</span>%</div>
  </div>

  <!-- Слайдер порога -->
  <div class="threshold-row">
    <label>Порог уверенности:</label>
    <input type="range" id="threshSlider" min="1" max="99" value="50"
           oninput="onThreshChange(this.value)">
    <span id="threshVal">0.50</span>
  </div>

  <!-- График -->
  <div class="chart-wrap">
    <h2>📈 Заполненность по времени (%)</h2>
    <canvas id="chart"></canvas>
  </div>

<script>
  // ── График ──────────────────────────────────────────────────
  const ctx   = document.getElementById('chart').getContext('2d');
  const MAX_POINTS = 60;

  const chartData = {
    labels: [],
    datasets: [
      {
        label: 'Занято %',
        data: [],
        borderColor: '#ff4444',
        backgroundColor: 'rgba(255,68,68,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2
      },
      {
        label: 'Свободно %',
        data: [],
        borderColor: '#00ff88',
        backgroundColor: 'rgba(0,255,136,0.06)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2
      }
    ]
  };

  const chart = new Chart(ctx, {
    type: 'line',
    data: chartData,
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: { color:'#666', maxTicksLimit: 10, font:{size:11} },
          grid:  { color:'#222' }
        },
        y: {
          min: 0, max: 100,
          ticks: { color:'#666', callback: v => v + '%', font:{size:11} },
          grid:  { color:'#222' }
        }
      },
      plugins: {
        legend: { labels:{ color:'#aaa', font:{size:12} } }
      }
    }
  });

  function pushChartPoint(label, pct) {
    const freePct = 100 - pct;
    chartData.labels.push(label);
    chartData.datasets[0].data.push(pct);
    chartData.datasets[1].data.push(freePct);
    if (chartData.labels.length > MAX_POINTS) {
      chartData.labels.shift();
      chartData.datasets[0].data.shift();
      chartData.datasets[1].data.shift();
    }
    chart.update();
  }

  // ── Статистика ─────────────────────────────────────────────
  function updateStats() {
    fetch('/stats')
      .then(r => r.json())
      .then(d => {
        document.getElementById('free').textContent     = d.free;
        document.getElementById('occupied').textContent = d.occupied;
        document.getElementById('pct').textContent      = d.pct;
        pushChartPoint(d.time || new Date().toLocaleTimeString(), d.pct);
      });
  }
  setInterval(updateStats, 1000);
  updateStats();

  // ── Порог ──────────────────────────────────────────────────
  function onThreshChange(val) {
    const v = (parseInt(val) / 100).toFixed(2);
    document.getElementById('threshVal').textContent = v;
    fetch('/set_threshold', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({threshold: parseFloat(v)})
    });
  }

  // ── Парковки ───────────────────────────────────────────────
  fetch('/parkings')
    .then(r => r.json())
    .then(data => {
      const sel = document.getElementById('parkingSelect');
      data.forEach(p => {
        const opt = document.createElement('option');
        opt.value       = p.label;
        opt.textContent = p.label;
        sel.appendChild(opt);
      });
      // Автовыбор из URL-параметра ?parking=label (переход с карты)
      const urlParam = new URLSearchParams(window.location.search).get('parking');
      if (urlParam && data.find(p => p.label === urlParam)) {
        sel.value = urlParam;
        changeParking();
      } else if (data.length === 1) {
        sel.value = data[0].label;
        changeParking();
      }
    });

  function changeParking() {
    const val = document.getElementById('parkingSelect').value;
    if (!val) return;
    fetch('/set_parking', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({label: val})
    }).then(() => reloadFeed());
  }

  function reloadFeed() {
    document.getElementById('feed').src = '/video_feed?' + Date.now();
  }

  // ── CSV ────────────────────────────────────────────────────
  function exportCSV() {
    window.location.href = '/export_csv';
  }
</script>
</body>
</html>
'''


# ── Маршруты ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


@app.route('/stats')
def stats():
    s = dict(latest_stats)
    s['time'] = datetime.now().strftime('%H:%M:%S')
    return jsonify(s)


@app.route('/parkings')
def parkings():
    return jsonify(get_available_parkings())


@app.route('/set_parking', methods=['POST'])
def set_parking():
    global current_video, current_spots
    data  = request.get_json()
    label = data.get('label')
    for p in get_available_parkings():
        if p['label'] == label:
            current_video = p['video']
            current_spots = p['spots']
            stats_history.clear()   # сбрасываем историю при смене парковки
            return jsonify(ok=True)
    return jsonify(ok=False, error='Парковка не найдена')


@app.route('/set_threshold', methods=['POST'])
def set_threshold():
    global current_threshold
    data = request.get_json()
    val  = data.get('threshold', 0.5)
    current_threshold = max(0.01, min(0.99, float(val)))
    return jsonify(ok=True, threshold=current_threshold)


@app.route('/export_csv')
def export_csv():
    if not stats_history:
        return "Нет данных для экспорта", 204

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['time', 'free', 'occupied', 'pct'])
    writer.writeheader()
    writer.writerows(stats_history)

    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename=parking_stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )
    return response


@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(current_video, current_spots),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


if __name__ == '__main__':
    app.run(debug=True)
