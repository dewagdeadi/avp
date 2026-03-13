"""
SQLite database for KlipNyimak — stores processed videos and job history.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "downloads", "klipnyimak.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS processed_videos (
            video_id    TEXT PRIMARY KEY,
            title       TEXT NOT NULL DEFAULT '',
            url         TEXT NOT NULL DEFAULT '',
            channel     TEXT NOT NULL DEFAULT '',
            view_count  INTEGER DEFAULT 0,
            status      TEXT NOT NULL DEFAULT 'processed',
            job_id      TEXT DEFAULT '',
            processed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id      TEXT PRIMARY KEY,
            video_id    TEXT DEFAULT '',
            youtube_url TEXT NOT NULL DEFAULT '',
            title       TEXT NOT NULL DEFAULT '',
            channel     TEXT NOT NULL DEFAULT '',
            hook_text   TEXT DEFAULT '',
            detail      TEXT DEFAULT '',
            file_mb     REAL DEFAULT 0,
            status      TEXT NOT NULL DEFAULT 'completed',
            auto        INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ── Processed videos ──────────────────────────────────────────────────────────

def is_processed(video_id: str) -> bool:
    conn = _get_conn()
    row = conn.execute("SELECT 1 FROM processed_videos WHERE video_id = ?", (video_id,)).fetchone()
    conn.close()
    return row is not None


def get_processed_ids() -> set:
    conn = _get_conn()
    rows = conn.execute("SELECT video_id FROM processed_videos").fetchall()
    conn.close()
    return {r["video_id"] for r in rows}


def add_processed(video_id: str, title: str = "", url: str = "",
                  channel: str = "", view_count: int = 0,
                  status: str = "processed", job_id: str = ""):
    conn = _get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO processed_videos
            (video_id, title, url, channel, view_count, status, job_id, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (video_id, title, url, channel, view_count, status, job_id,
          datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_all_processed() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM processed_videos ORDER BY processed_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Jobs ──────────────────────────────────────────────────────────────────────

def add_job(job_id: str, video_id: str = "", youtube_url: str = "",
            title: str = "", channel: str = "", hook_text: str = "",
            detail: str = "", file_mb: float = 0, auto: bool = False):
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO jobs
            (job_id, video_id, youtube_url, title, channel, hook_text,
             detail, file_mb, status, auto, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)
    """, (job_id, video_id, youtube_url, title, channel, hook_text,
          detail, file_mb, 1 if auto else 0, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_all_jobs() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Migration ─────────────────────────────────────────────────────────────────

def migrate_from_json(history_file: str):
    """One-time migration from auto_history.json to SQLite."""
    import json
    if not os.path.isfile(history_file):
        return

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    entries = []
    if "processed" in data:
        entries = data["processed"]
    elif "processed_ids" in data:
        for vid_id in data["processed_ids"]:
            entries.append({"id": vid_id})

    for e in entries:
        vid_id = e.get("id", "")
        if vid_id:
            add_processed(
                video_id=vid_id,
                title=e.get("title", ""),
                url=e.get("url", f"https://www.youtube.com/watch?v={vid_id}"),
                status="migrated",
            )

    # Rename old file so we don't re-migrate
    os.rename(history_file, history_file + ".bak")
    print(f"[db] Migrated {len(entries)} entries from JSON to SQLite")


# ── Init on import ────────────────────────────────────────────────────────────
init_db()
