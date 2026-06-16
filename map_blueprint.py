import os
import json
import base64
import cv2
from flask import Blueprint, jsonify, request, render_template_string

map_bp = Blueprint('map', __name__, url_prefix='/map')

LOCATIONS_FILE = 'locations.json'
UPLOAD_FOLDER  = 'vid_frags'
SPOTS_FOLDER   = 'spots'


# ── Утилиты ────────────────────────────────────────────────────────────────

def load_locations():
    if not os.path.exists(LOCATIONS_FILE):
        return []
    with open(LOCATIONS_FILE, encoding='utf-8') as f:
        return json.load(f)


def save_locations(data):
    with open(LOCATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_available_videos():
    """Возвращает список видео у которых есть файл разметки."""
    result = []
    if not os.path.exists(UPLOAD_FOLDER):
        return result
    for fname in sorted(os.listdir(UPLOAD_FOLDER)):
        if not fname.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            continue
        label = os.path.splitext(fname)[0]
        spots_path = os.path.join(SPOTS_FOLDER, label + '.txt')
        result.append({
            'label': label,
            'video': os.path.join(UPLOAD_FOLDER, fname),
            'has_spots': os.path.exists(spots_path),
        })
    return result


# ── HTML ───────────────────────────────────────────────────────────────────

MAP_HTML = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Карта парковок</title>

  <!-- Leaflet -->
  <link  rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>

  <style>
    * { margin:0; padding:0; box-sizing:border-box; }

    body {
      background:#1a1a2e; color:#eee;
      font-family:'Segoe UI',sans-serif;
      display:flex; flex-direction:column;
      height:100vh; overflow:hidden;
    }

    /* ── шапка ── */
    .topbar {
      display:flex; align-items:center; gap:16px;
      padding:10px 20px;
      background:#12122a;
      border-bottom:1px solid #00d4ff22;
      flex-shrink:0;
    }
    .topbar h1 { font-size:18px; color:#00d4ff; letter-spacing:1px; }
    .topbar .spacer { flex:1; }
    .btn {
      padding:7px 18px; border-radius:6px; border:none;
      font-size:13px; cursor:pointer; font-weight:600;
      transition:opacity .15s;
    }
    .btn:hover { opacity:.82; }
    .btn-primary  { background:#00d4ff; color:#111; }
    .btn-success  { background:#00cc66; color:#111; }
    .btn-warning  { background:#ffaa00; color:#111; }
    .btn-danger   { background:#ff4444; color:#fff; }
    .btn-back     { background:#2a2a4a; color:#aaa; border:1px solid #444; }
    .btn.active   { outline:2px solid #fff; }

    /* ── режим добавления ── */
    #addMode {
      display:none;
      align-items:center; gap:12px;
      padding:8px 20px;
      background:#1a2a1a;
      border-bottom:1px solid #00cc6633;
      font-size:13px; color:#aaa;
      flex-shrink:0;
    }
    #addMode.visible { display:flex; }
    #addMode select, #addMode input {
      background:#2a2a4a; color:#eee;
      border:1px solid #00d4ff44; border-radius:5px;
      padding:5px 10px; font-size:13px;
    }
    #addMode .hint { color:#666; font-size:12px; }

    /* ── карта ── */
    #map { flex:1; }

    /* ── Popup стиль ── */
    .leaflet-popup-content-wrapper {
      background:#1e1e3a !important;
      border:1px solid #00d4ff44 !important;
      border-radius:10px !important;
      box-shadow:0 0 20px #00d4ff22 !important;
      color:#eee !important;
    }
    .leaflet-popup-tip { background:#1e1e3a !important; }
    .leaflet-popup-content { margin:0 !important; padding:0 !important; }

    .popup-wrap {
      width:260px;
      padding:14px;
      font-family:'Segoe UI',sans-serif;
    }
    .popup-wrap .p-name {
      font-size:15px; font-weight:700; color:#00d4ff;
      margin-bottom:10px;
    }
    .popup-preview {
      width:100%; border-radius:6px;
      border:1px solid #00d4ff33;
      margin-bottom:10px;
      display:block;
    }
    .popup-stats {
      display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap;
    }
    .stat-badge {
      flex:1; min-width:70px;
      padding:6px 0; border-radius:6px;
      text-align:center; font-size:12px; font-weight:700;
    }
    .stat-free     { background:#1a472a; color:#00ff88; border:1px solid #00ff8844; }
    .stat-occupied { background:#4a1a1a; color:#ff4444; border:1px solid #ff444444; }
    .stat-pct      { background:#1a2a47; color:#00d4ff; border:1px solid #00d4ff44; }
    .popup-wrap .p-btn {
      display:block; width:100%;
      padding:8px; border-radius:6px;
      background:#00d4ff; color:#111;
      font-weight:700; font-size:13px;
      text-align:center; text-decoration:none;
      border:none; cursor:pointer;
      transition:opacity .15s;
    }
    .popup-wrap .p-btn:hover { opacity:.85; }
    .popup-wrap .p-del {
      display:block; width:100%; margin-top:6px;
      padding:5px; border-radius:6px;
      background:#2a1a1a; color:#ff6666;
      font-size:11px; text-align:center;
      border:1px solid #ff444433; cursor:pointer;
    }
    .popup-wrap .p-del:hover { background:#3a1a1a; }

    /* ── подсказка курсора ── */
    #cursor-hint {
      display:none;
      position:fixed; bottom:24px; left:50%;
      transform:translateX(-50%);
      background:#ffaa00dd; color:#111;
      padding:8px 20px; border-radius:20px;
      font-size:13px; font-weight:600;
      pointer-events:none; z-index:9999;
    }
    #cursor-hint.visible { display:block; }
  </style>
</head>
<body>

<!-- Шапка -->
<div class="topbar">
  <h1>🗺 Карта парковок</h1>
  <div class="spacer"></div>
  <button class="btn btn-success" id="btnAddToggle" onclick="toggleAddMode()">➕ Добавить парковку</button>
  <a href="/"><button class="btn btn-back" type="button">← Мониторинг</button></a>
  <a href="/editor"><button class="btn btn-back" type="button">✏️ Редактор</button></a>
</div>

<!-- Панель режима добавления -->
<div id="addMode">
  <span style="color:#00cc66;font-weight:700">📍 Режим добавления:</span>
  <span class="hint">Выберите парковку → кликните по карте</span>
  <select id="selVideo">
    <option value="">— выберите парковку —</option>
  </select>
  <input type="text" id="inpName" placeholder="Название (необязательно)" style="width:180px">
  <button class="btn btn-danger btn-back" onclick="toggleAddMode()" style="background:#2a1a1a;color:#ff6666;border:1px solid #ff444433">✕ Отмена</button>
</div>

<!-- Карта -->
<div id="map"></div>

<!-- Подсказка -->
<div id="cursor-hint">📍 Кликните по карте, чтобы установить маркер</div>

<script>
// ── Инициализация карты ────────────────────────────────────────────────────
const map = L.map('map', { zoomControl:true }).setView([55.75, 37.62], 12);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

// Тёмная подложка через CSS-filter
map.getContainer().querySelector('canvas, .leaflet-tile-pane').style?.setProperty('filter','invert(0.9) hue-rotate(180deg)');
document.getElementById('map').style.filter = 'invert(0.92) hue-rotate(180deg) brightness(0.85)';

// ── Состояние ──────────────────────────────────────────────────────────────
let addModeActive = false;
let markers = {};        // label → leaflet marker
let statsCache = {};     // label → {free, occupied, pct}
let allLocations = [];

// ── Иконки маркеров ───────────────────────────────────────────────────────
function makeIcon(pct) {
  const color = pct === null ? '#888' : pct >= 80 ? '#ff4444' : pct >= 50 ? '#ffaa00' : '#00cc66';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="48" viewBox="0 0 36 48">
    <path d="M18 0C8.06 0 0 8.06 0 18c0 12.77 18 30 18 30S36 30.77 36 18C36 8.06 27.94 0 18 0z" fill="${color}"/>
    <circle cx="18" cy="18" r="10" fill="#fff"/>
    <text x="18" y="23" text-anchor="middle" font-size="11" font-weight="bold" fill="${color}" font-family="sans-serif">${pct !== null ? pct+'%' : '?'}</text>
  </svg>`;
  return L.divIcon({
    html: svg, className:'', iconSize:[36,48], iconAnchor:[18,48], popupAnchor:[0,-50]
  });
}

// ── Загрузка парковок ─────────────────────────────────────────────────────
async function loadLocations() {
  const res = await fetch('/map/locations');
  allLocations = await res.json();
  allLocations.forEach(addMarker);
  if (allLocations.length) {
    const bounds = allLocations.map(l => [l.lat, l.lng]);
    map.fitBounds(bounds, { padding:[60,60], maxZoom:15 });
  }
}

function addMarker(loc) {
  const marker = L.marker([loc.lat, loc.lng], { icon: makeIcon(null) }).addTo(map);
  marker._loc = loc;
  markers[loc.label] = marker;
  marker.bindPopup(() => buildPopup(loc.label, loc), { maxWidth:280, minWidth:260 });
  marker.on('popupopen', () => refreshPopupStats(loc.label));
}

// ── Построение попапа ─────────────────────────────────────────────────────
function buildPopup(label, loc) {
  const stats = statsCache[label] || {};
  const pct  = stats.pct  ?? '—';
  const free = stats.free ?? '—';
  const occ  = stats.occupied ?? '—';

  return `<div class="popup-wrap">
    <div class="p-name">🅿 ${loc.name || label}</div>
    <img class="popup-preview" id="prev-${label}"
         src="/map/preview/${label}?t=${Date.now()}"
         onerror="this.style.display='none'">
    <div class="popup-stats">
      <div class="stat-badge stat-free">🟢 Своб.<br>${free}</div>
      <div class="stat-badge stat-occupied">🔴 Занято<br>${occ}</div>
      <div class="stat-badge stat-pct">📊 Загр.<br>${pct}%</div>
    </div>
    <a class="p-btn" href="/?parking=${encodeURIComponent(label)}">▶ Открыть мониторинг</a>
    <div class="p-del" onclick="deleteLocation('${label}')">🗑 Удалить с карты</div>
  </div>`;
}

async function refreshPopupStats(label) {
  try {
    const res  = await fetch('/map/parking_stats/' + encodeURIComponent(label));
    const data = await res.json();
    statsCache[label] = data;
    // обновляем иконку
    if (markers[label]) markers[label].setIcon(makeIcon(data.pct ?? null));
    // обновляем попап если открыт
    const m = markers[label];
    if (m && m.isPopupOpen()) {
      const loc = allLocations.find(l => l.label === label);
      m.getPopup().setContent(buildPopup(label, loc));
    }
  } catch(e) {}
}

// ── Режим добавления маркера ──────────────────────────────────────────────
function toggleAddMode() {
  addModeActive = !addModeActive;
  document.getElementById('addMode').classList.toggle('visible', addModeActive);
  document.getElementById('cursor-hint').classList.toggle('visible', addModeActive);
  document.getElementById('btnAddToggle').classList.toggle('active', addModeActive);
  map.getContainer().style.cursor = addModeActive ? 'crosshair' : '';
}

map.on('click', async (e) => {
  if (!addModeActive) return;

  const label = document.getElementById('selVideo').value;
  if (!label) { alert('Сначала выберите парковку из списка'); return; }

  const name = document.getElementById('inpName').value.trim() || label;
  const { lat, lng } = e.latlng;

  // Проверяем, не привязана ли уже эта парковка
  const exists = allLocations.find(l => l.label === label);
  if (exists) {
    if (!confirm(`Парковка «${label}» уже на карте. Переместить маркер?`)) return;
    await deleteLocation(label, true);
  }

  const loc = { label, name, lat, lng };
  const res  = await fetch('/map/set_location', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(loc)
  });
  const data = await res.json();
  if (data.ok) {
    allLocations = allLocations.filter(l => l.label !== label);
    allLocations.push(loc);
    addMarker(loc);
    toggleAddMode();
    document.getElementById('selVideo').value = '';
    document.getElementById('inpName').value  = '';
    markers[label].openPopup();
  } else {
    alert('Ошибка: ' + data.error);
  }
});

async function deleteLocation(label, silent = false) {
  if (!silent && !confirm(`Удалить парковку «${label}» с карты?`)) return;
  const res  = await fetch('/map/delete_location', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ label })
  });
  const data = await res.json();
  if (data.ok) {
    if (markers[label]) { markers[label].remove(); delete markers[label]; }
    allLocations = allLocations.filter(l => l.label !== label);
  }
}

// ── Загрузка списка видео в select ────────────────────────────────────────
async function loadVideoList() {
  const res  = await fetch('/map/videos');
  const list = await res.json();
  const sel  = document.getElementById('selVideo');
  list.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.label;
    opt.textContent = v.label + (v.has_spots ? '' : ' (нет разметки)');
    if (!v.has_spots) opt.style.color = '#888';
    sel.appendChild(opt);
  });
}

// ── Периодическое обновление иконок ──────────────────────────────────────
async function refreshAllStats() {
  for (const loc of allLocations) {
    await refreshPopupStats(loc.label);
  }
}

// ── Инициализация ─────────────────────────────────────────────────────────
loadLocations();
loadVideoList();
setInterval(refreshAllStats, 5000);   // обновляем иконки каждые 5 сек
</script>
</body>
</html>
"""


# ── Маршруты ───────────────────────────────────────────────────────────────

@map_bp.route('/')
def map_page():
    return render_template_string(MAP_HTML)


@map_bp.route('/locations')
def get_locations():
    return jsonify(load_locations())


@map_bp.route('/videos')
def get_videos():
    return jsonify(get_available_videos())


@map_bp.route('/set_location', methods=['POST'])
def set_location():
    data  = request.get_json()
    label = data.get('label')
    lat   = data.get('lat')
    lng   = data.get('lng')
    name  = data.get('name', label)

    if not label or lat is None or lng is None:
        return jsonify(ok=False, error='Не переданы обязательные поля')

    locations = load_locations()
    locations = [l for l in locations if l['label'] != label]   # убираем старый
    locations.append({'label': label, 'name': name, 'lat': lat, 'lng': lng})
    save_locations(locations)
    return jsonify(ok=True)


@map_bp.route('/delete_location', methods=['POST'])
def delete_location():
    data  = request.get_json()
    label = data.get('label')
    if not label:
        return jsonify(ok=False, error='Не передан label')

    locations = [l for l in load_locations() if l['label'] != label]
    save_locations(locations)
    return jsonify(ok=True)


@map_bp.route('/preview/<label>')
def preview(label):
    """Возвращает первый кадр видео для парковки в base64 JPEG."""
    video_path = None
    for fname in os.listdir(UPLOAD_FOLDER) if os.path.exists(UPLOAD_FOLDER) else []:
        if os.path.splitext(fname)[0] == label:
            video_path = os.path.join(UPLOAD_FOLDER, fname)
            break

    if not video_path:
        return '', 404

    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return '', 404

    # Уменьшаем для превью
    h, w = frame.shape[:2]
    max_w = 480
    if w > max_w:
        scale = max_w / w
        frame = cv2.resize(frame, (max_w, int(h * scale)))

    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    img_b64 = base64.b64encode(buf).decode('utf-8')

    from flask import Response
    return Response(
        base64.b64decode(img_b64),
        mimetype='image/jpeg',
        headers={'Cache-Control': 'no-cache'}
    )


@map_bp.route('/parking_stats/<label>')
def parking_stats(label):
    """Текущая статистика для конкретной парковки (берём из глобального состояния app.py)."""
    # Импортируем глобальное состояние из app.py
    try:
        import app as main_app
        if main_app.current_video and label in main_app.current_video:
            s = dict(main_app.latest_stats)
            return jsonify(s)
    except Exception:
        pass
    # Если эта парковка не активна — возвращаем пустую статистику
    return jsonify({'free': None, 'occupied': None, 'pct': None})
