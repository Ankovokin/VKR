import os
import base64
import json
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, render_template_string

editor_bp = Blueprint('editor', __name__, url_prefix='/editor')

UPLOAD_FOLDER = 'vid_frags'
SPOTS_FOLDER = 'spots'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SPOTS_FOLDER, exist_ok=True)

EDITOR_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Редактор разметки парковки</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #1a1a2e;
      color: #eee;
      font-family: 'Segoe UI', sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px;
      gap: 16px;
    }
    h1 { color: #00d4ff; font-size: 22px; letter-spacing: 1px; }

    .toolbar {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: center;
    }
    .btn {
      padding: 8px 20px;
      border-radius: 6px;
      border: none;
      font-size: 14px;
      cursor: pointer;
      transition: opacity .15s;
    }
    .btn:hover { opacity: .85; }
    .btn-primary  { background: #00d4ff; color: #111; font-weight: 600; }
    .btn-danger   { background: #ff4444; color: #fff; }
    .btn-success  { background: #00cc66; color: #111; font-weight: 600; }
    .btn-warning  { background: #ffaa00; color: #111; }
    .btn-secondary{ background: #444; color: #eee; }
    .btn-back     { background: #2a2a4a; color: #aaa; border: 1px solid #444; }
    .btn.active   { outline: 2px solid #fff; }

    .upload-row {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    input[type=file] { display: none; }
    .file-label {
      padding: 8px 20px;
      background: #2a2a4a;
      border: 1px dashed #00d4ff88;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      color: #00d4ff;
    }
    .file-label:hover { background: #2a2a5e; }

    .canvas-wrap {
      position: relative;
      border: 2px solid #00d4ff33;
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 0 30px #00d4ff22;
      display: none;
    }
    #bgImg {
      display: block;
      max-width: 900px;
      width: 100%;
    }
    #canvas {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      cursor: crosshair;
    }
    #canvas.delete-mode { cursor: pointer; }

    .status-bar {
      display: flex;
      gap: 24px;
      font-size: 14px;
      color: #aaa;
    }
    .status-bar span { color: #fff; font-weight: 600; }

    .hint {
      font-size: 12px;
      color: #666;
      text-align: center;
    }

    #saveStatus {
      font-size: 13px;
      padding: 6px 16px;
      border-radius: 6px;
      display: none;
    }
    #saveStatus.ok  { background: #1a472a; color: #00ff88; display: block; }
    #saveStatus.err { background: #4a1a1a; color: #ff4444; display: block; }
  </style>
</head>
<body>
  <h1>🅿 Редактор разметки парковочных мест</h1>

  <div class="upload-row">
    <label class="file-label" for="videoFile">📂 Выбрать видео</label>
    <input type="file" id="videoFile" accept="video/*">
    <span id="fileName" style="font-size:13px;color:#888">файл не выбран</span>
    <button class="btn btn-primary" onclick="uploadVideo()">Загрузить</button>
  </div>

  <div class="toolbar" id="toolbar" style="display:none">
    <button class="btn btn-secondary active" id="btnDraw" onclick="setMode('draw')">✏️ Рисовать</button>
    <button class="btn btn-danger"  id="btnDel"  onclick="setMode('delete')">🗑 Удалять</button>
    <button class="btn btn-warning"             onclick="undoLast()">↩ Отменить</button>
    <button class="btn btn-danger"              onclick="clearAll()">✕ Очистить всё</button>
    <button class="btn btn-secondary"           onclick="toggleNumbers()">🔢 Номера</button>
    <button class="btn btn-success"             onclick="saveSpots()">💾 Сохранить разметку</button>
    <a href="/"><button class="btn btn-back" type="button">← На главную</button></a>
  </div>

  <div class="status-bar" id="statusBar" style="display:none">
    Мест: <span id="spotCount">0</span>
    &nbsp;|&nbsp; Режим: <span id="modeLabel">Рисование</span>
    &nbsp;|&nbsp; Видео: <span id="videoName">—</span>
    &nbsp;|&nbsp; <span style="color:#aaa;font-size:12px">ESC — выйти из режима</span>
  </div>

  <div class="canvas-wrap" id="canvasWrap">
    <img id="bgImg" alt="кадр видео">
    <canvas id="canvas"></canvas>
  </div>

  <div id="saveStatus"></div>
  <div class="hint">Зажми левую кнопку мыши и протяни, чтобы нарисовать место.&nbsp;&nbsp;В режиме удаления — кликни по прямоугольнику.&nbsp;&nbsp;ESC — сброс режима.</div>

<script>
  let spots = [];
  let drawing = false;
  let startX, startY;
  let mode = 'draw';
  let showNumbers = true;
  let currentVideo = null;
  let scaleX = 1, scaleY = 1;
  let naturalW = 0, naturalH = 0;

  const canvas  = document.getElementById('canvas');
  const ctx     = canvas.getContext('2d');
  const bgImg   = document.getElementById('bgImg');
  const wrap    = document.getElementById('canvasWrap');

  // ── Загрузка видео ──────────────────────────────────────────
  document.getElementById('videoFile').addEventListener('change', e => {
    const name = e.target.files[0]?.name || 'файл не выбран';
    document.getElementById('fileName').textContent = name;
  });

  async function uploadVideo() {
    const file = document.getElementById('videoFile').files[0];
    if (!file) return alert('Выберите видеофайл');

    const fd = new FormData();
    fd.append('video', file);

    const res  = await fetch('/editor/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!data.ok) return alert('Ошибка загрузки: ' + data.error);

    currentVideo = data.filename;
    naturalW     = data.width;
    naturalH     = data.height;

    bgImg.src = 'data:image/jpeg;base64,' + data.frame;
    bgImg.onload = () => {
      // Показываем обёртку сначала, потом ждём следующий кадр рендера
      // чтобы offsetWidth был уже посчитан браузером
      wrap.style.display = 'block';
      document.getElementById('toolbar').style.display = 'flex';
      document.getElementById('statusBar').style.display = 'flex';
      document.getElementById('videoName').textContent = currentVideo;

      requestAnimationFrame(() => {
        syncCanvas();
        loadExistingSpots();
      });
    };
  }

  function syncCanvas() {
    // Canvas рисуем в натуральных пикселях картинки — 1:1 с кадром
    // Масштабирование для отображения делает CSS через width:100%
    canvas.width  = naturalW;
    canvas.height = naturalH;
    // scaleX/scaleY теперь всегда 1 — координаты хранятся и рисуются
    // сразу в реальных пикселях кадра, CSS сжимает весь canvas-элемент
    scaleX = 1;
    scaleY = 1;
    canvas.style.width  = bgImg.offsetWidth  + 'px';
    canvas.style.height = bgImg.offsetHeight + 'px';
    redraw();
  }

  window.addEventListener('resize', () => {
    if (!naturalW) return;
    canvas.style.width  = bgImg.offsetWidth  + 'px';
    canvas.style.height = bgImg.offsetHeight + 'px';
    redraw();
  });

  async function loadExistingSpots() {
    const res  = await fetch('/editor/spots/' + currentVideo);
    const data = await res.json();
    if (data.spots && data.spots.length) {
      spots = data.spots;
      updateCount();
      redraw();
    }
  }

  // ── Координаты мыши → реальные пиксели кадра ───────────────
  // canvas.width/height = натуральный размер кадра (напр. 1920×1080)
  // rect.width/height   = CSS-размер элемента на экране (напр. 900×506)
  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (canvas.width  / rect.width),
      y: (e.clientY - rect.top)  * (canvas.height / rect.height)
    };
  }

  // ── События мыши ───────────────────────────────────────────
  canvas.addEventListener('mousedown', e => {
    const pos = getPos(e);
    if (mode === 'delete') {
      deleteAtPoint(pos.x, pos.y);
      return;
    }
    drawing = true;
    startX = pos.x;
    startY = pos.y;
  });

  canvas.addEventListener('mousemove', e => {
    if (!drawing) return;
    const pos = getPos(e);
    redraw();
    ctx.strokeStyle = '#ffff00';
    ctx.lineWidth = 2;
    ctx.strokeRect(startX, startY, pos.x - startX, pos.y - startY);
  });

  canvas.addEventListener('mouseup', e => {
    if (!drawing) return;
    drawing = false;
    const pos = getPos(e);
    const x1 = Math.min(startX, pos.x), x2 = Math.max(startX, pos.x);
    const y1 = Math.min(startY, pos.y), y2 = Math.max(startY, pos.y);
    if ((x2 - x1) > 10 && (y2 - y1) > 10) {
      // Сохраняем в реальных координатах кадра
      spots.push({
        x1: Math.round(x1 * scaleX),
        y1: Math.round(y1 * scaleY),
        x2: Math.round(x2 * scaleX),
        y2: Math.round(y2 * scaleY)
      });
      updateCount();
    }
    redraw();
  });

  canvas.addEventListener('mouseleave', () => {
    if (drawing) { drawing = false; redraw(); }
  });

  // ── Удаление ───────────────────────────────────────────────
  function deleteAtPoint(cx, cy) {
    // cx/cy в canvas-координатах, spots в реальных — конвертируем
    const rx = cx * scaleX, ry = cy * scaleY;
    const idx = spots.findIndex(s => rx >= s.x1 && rx <= s.x2 && ry >= s.y1 && ry <= s.y2);
    if (idx !== -1) { spots.splice(idx, 1); updateCount(); redraw(); }
  }

  // ── Отрисовка ──────────────────────────────────────────────
  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    spots.forEach((s, i) => {
      // spots хранятся в реальных координатах кадра = координатам canvas
      const cw = s.x2 - s.x1;
      const ch = s.y2 - s.y1;
      ctx.strokeStyle = mode === 'delete' ? '#ff6666' : '#00ff88';
      ctx.lineWidth = Math.max(2, canvas.width / 500); // толщина под размер кадра
      ctx.strokeRect(s.x1, s.y1, cw, ch);
      if (showNumbers) {
        ctx.fillStyle = mode === 'delete' ? '#ff6666' : '#00ff88';
        const fontSize = Math.max(14, Math.round(canvas.width / 80));
        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.fillText(i + 1, s.x1 + 4, s.y1 + fontSize + 2);
      }
    });
  }

  // ── Управление ─────────────────────────────────────────────
  function setMode(m) {
    mode = m;
    canvas.className = m === 'delete' ? 'delete-mode' : '';
    document.getElementById('btnDraw').classList.toggle('active', m === 'draw');
    document.getElementById('btnDel').classList.toggle('active',  m === 'delete');
    document.getElementById('modeLabel').textContent = m === 'draw' ? 'Рисование' : 'Удаление';
    redraw();
  }

  // ESC — сброс в режим рисования, отмена незавершённого прямоугольника
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      drawing = false;
      setMode('draw');
      redraw();
    }
  });

  function undoLast() {
    if (spots.length) { spots.pop(); updateCount(); redraw(); }
  }

  function clearAll() {
    if (!spots.length) return;
    if (confirm('Удалить все ' + spots.length + ' мест?')) {
      spots = []; updateCount(); redraw();
    }
  }

  function toggleNumbers() {
    showNumbers = !showNumbers; redraw();
  }

  function updateCount() {
    document.getElementById('spotCount').textContent = spots.length;
  }

  // ── Сохранение ─────────────────────────────────────────────
  async function saveSpots() {
    if (!currentVideo) return alert('Сначала загрузите видео');
    if (!spots.length)  return alert('Нет размеченных мест');

    const res  = await fetch('/editor/save_spots', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: currentVideo, spots })
    });
    const data = await res.json();
    const el   = document.getElementById('saveStatus');
    if (data.ok) {
      el.className   = 'ok';
      el.textContent = `✓ Сохранено ${spots.length} мест → ${data.path}`;
    } else {
      el.className   = 'err';
      el.textContent = '✗ Ошибка: ' + data.error;
    }
    setTimeout(() => el.style.display = 'none', 4000);
  }
</script>
</body>
</html>
'''


@editor_bp.route('/')
def editor():
    return render_template_string(EDITOR_HTML)


@editor_bp.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify(ok=False, error='Файл не передан')

    file = request.files['video']
    if not file.filename:
        return jsonify(ok=False, error='Пустое имя файла')

    # Сохраняем видео
    filename = file.filename
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # Читаем первый кадр
    cap = cv2.VideoCapture(save_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return jsonify(ok=False, error='Не удалось прочитать видео')

    h, w = frame.shape[:2]

    # Кодируем кадр в base64 JPEG
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_b64 = base64.b64encode(buf).decode('utf-8')

    return jsonify(ok=True, filename=filename, frame=frame_b64, width=w, height=h)


@editor_bp.route('/spots/<filename>')
def get_spots(filename):
    """Возвращает существующую разметку для видео если есть"""
    spots_name = os.path.splitext(filename)[0] + '.txt'
    spots_path = os.path.join(SPOTS_FOLDER, spots_name)

    if not os.path.exists(spots_path):
        return jsonify(spots=[])

    spots = []
    with open(spots_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                x1, y1, x2, y2 = map(int, line.split(','))
                spots.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except ValueError:
                continue

    return jsonify(spots=spots)


@editor_bp.route('/save_spots', methods=['POST'])
def save_spots():
    data = request.get_json()
    filename = data.get('filename')
    spots = data.get('spots', [])

    if not filename:
        return jsonify(ok=False, error='Не передано имя файла')
    if not spots:
        return jsonify(ok=False, error='Нет мест для сохранения')

    spots_name = os.path.splitext(filename)[0] + '.txt'
    spots_path = os.path.join(SPOTS_FOLDER, spots_name)

    with open(spots_path, 'w') as f:
        for s in spots:
            f.write(f"{s['x1']},{s['y1']},{s['x2']},{s['y2']}\n")

    return jsonify(ok=True, path=spots_path, count=len(spots))
