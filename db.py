"""
db.py — работа с SQLite базой данных.

Таблицы:
  parkings      — метаданные парковок (название, адрес, координаты, путь к видео)
  stats_history — история статистики (свободно/занято/% по времени)
"""

import sqlite3
import os
import json
from contextlib import contextmanager

DB_PATH        = 'parking.db'
LOCATIONS_FILE = 'locations.json'


# ── Контекстный менеджер соединения ────────────────────────────────────────

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Инициализация схемы ────────────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS parkings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                address     TEXT    DEFAULT '',
                lat         REAL,
                lng         REAL,
                video_path  TEXT    NOT NULL,
                spots_path  TEXT    NOT NULL,
                total_spots INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS stats_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                parking_id  INTEGER NOT NULL REFERENCES parkings(id) ON DELETE CASCADE,
                ts          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                free        INTEGER NOT NULL,
                occupied    INTEGER NOT NULL,
                total       INTEGER NOT NULL,
                pct         INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_stats_parking_ts
                ON stats_history (parking_id, ts);
        """)
    _migrate_locations()


# ── Миграция из locations.json ─────────────────────────────────────────────

def _migrate_locations():
    if not os.path.exists(LOCATIONS_FILE):
        return
    with open(LOCATIONS_FILE, encoding='utf-8') as f:
        locations = json.load(f)
    if not locations:
        return
    with get_conn() as conn:
        for loc in locations:
            label      = loc.get('label', '')
            video_path = _find_video(label)
            spots_path = os.path.join('spots', label + '.txt')
            if not label or not video_path:
                continue
            conn.execute("""
                INSERT OR IGNORE INTO parkings
                    (label, name, lat, lng, video_path, spots_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (label, loc.get('name', label), loc.get('lat'),
                  loc.get('lng'), video_path, spots_path))
    print(f"[db] Мигрировано {len(locations)} парковок из {LOCATIONS_FILE}")


def _find_video(label):
    folder = 'vid_frags'
    if not os.path.exists(folder):
        return None
    for fname in os.listdir(folder):
        if os.path.splitext(fname)[0] == label:
            return os.path.join(folder, fname)
    return None


# ── CRUD: парковки ─────────────────────────────────────────────────────────

def get_all_parkings():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM parkings ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_parking_by_label(label):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM parkings WHERE label = ?", (label,)
        ).fetchone()
    return dict(row) if row else None


def upsert_parking(label, name, lat=None, lng=None,
                   address='', video_path=None, spots_path=None):
    if video_path is None:
        video_path = _find_video(label) or ''
    if spots_path is None:
        spots_path = os.path.join('spots', label + '.txt')
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO parkings (label, name, address, lat, lng, video_path, spots_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(label) DO UPDATE SET
                name       = excluded.name,
                address    = excluded.address,
                lat        = excluded.lat,
                lng        = excluded.lng,
                video_path = excluded.video_path,
                spots_path = excluded.spots_path
        """, (label, name, address, lat, lng, video_path, spots_path))


def delete_parking(label):
    with get_conn() as conn:
        conn.execute("DELETE FROM parkings WHERE label = ?", (label,))


def update_total_spots(label, total):
    with get_conn() as conn:
        conn.execute(
            "UPDATE parkings SET total_spots = ? WHERE label = ?", (total, label)
        )


# ── CRUD: история статистики ───────────────────────────────────────────────

def add_stat(label, free, occupied, total, pct):
    """Добавляет одну запись. Вызывается из generate_frames каждый кадр."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM parkings WHERE label = ?", (label,)
        ).fetchone()
        if not row:
            return
        conn.execute("""
            INSERT INTO stats_history (parking_id, free, occupied, total, pct)
            VALUES (?, ?, ?, ?, ?)
        """, (row['id'], free, occupied, total, pct))


def get_stats(label, period='day', limit=500):
    """
    История статистики за период.
    period: 'hour' | 'day' | 'week' | 'month'
    """
    period_sql = {
        'hour':  "-1 hours",
        'day':   "-1 days",
        'week':  "-7 days",
        'month': "-30 days",
    }.get(period, "-1 days")

    interval_map = {'hour': 1, 'day': 60, 'week': 3600, 'month': 7200}
    interval = interval_map.get(period, 60)

    with get_conn() as conn:
        parking = conn.execute(
            "SELECT id FROM parkings WHERE label = ?", (label,)
        ).fetchone()
        if not parking:
            return []

        if interval == 1:
            rows = conn.execute("""
                SELECT ts, free, occupied, pct
                FROM stats_history
                WHERE parking_id = ?
                  AND ts >= datetime('now', 'localtime', ?)
                ORDER BY ts LIMIT ?
            """, (parking['id'], period_sql, limit)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT
                    strftime('%Y-%m-%d %H:%M', ts) as ts,
                    ROUND(AVG(free))     as free,
                    ROUND(AVG(occupied)) as occupied,
                    ROUND(AVG(pct))      as pct
                FROM stats_history
                WHERE parking_id = ?
                  AND ts >= datetime('now', 'localtime', ?)
                GROUP BY (cast(strftime('%s', ts) as integer) / {interval})
                ORDER BY ts LIMIT ?
            """, (parking['id'], period_sql, limit)).fetchall()

    return [dict(r) for r in rows]


def get_peak_hours(label):
    """Средняя загруженность по часам суток (0–23) за всё время."""
    with get_conn() as conn:
        parking = conn.execute(
            "SELECT id FROM parkings WHERE label = ?", (label,)
        ).fetchone()
        if not parking:
            return []
        rows = conn.execute("""
            SELECT CAST(strftime('%H', ts) AS INTEGER) as hour,
                   ROUND(AVG(pct), 1) as avg_pct
            FROM stats_history WHERE parking_id = ?
            GROUP BY hour ORDER BY hour
        """, (parking['id'],)).fetchall()
    return [dict(r) for r in rows]


def get_summary(label):
    """Сводка за последние 24 часа."""
    with get_conn() as conn:
        parking = conn.execute(
            "SELECT id FROM parkings WHERE label = ?", (label,)
        ).fetchone()
        if not parking:
            return {}
        row = conn.execute("""
            SELECT ROUND(AVG(pct), 1) as avg_pct,
                   MIN(pct) as min_pct, MAX(pct) as max_pct,
                   COUNT(*) as records
            FROM stats_history
            WHERE parking_id = ?
              AND ts >= datetime('now', 'localtime', '-1 days')
        """, (parking['id'],)).fetchone()
    return dict(row) if row else {}
