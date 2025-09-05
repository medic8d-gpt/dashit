import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


# Resolve DB path priority (when DB_PATH not set):
# 1. Existing legacy root rss_feed_data.db (backward compatibility)
# 2. New location: <project_root>/database/rss_feed_data.db
def _default_db_path() -> str:
    project_root = Path(__file__).resolve().parent.parent
    legacy = project_root / 'rss_feed_data.db'
    if legacy.exists():
        return str(legacy)
    db_dir = project_root / 'database'
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / 'rss_feed_data.db')


def get_db_path() -> str:
    env_path = os.getenv('DB_PATH')
    if env_path:
        # If relative, resolve relative to the current working directory
        p = Path(env_path)
        return str(p if p.is_absolute() else (Path.cwd() / p).resolve())
    return _default_db_path()


_INIT_DONE = False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rss_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE,
                source TEXT,
                url TEXT,
                headline TEXT,
                summary TEXT,
                published TEXT,
                posted INTEGER DEFAULT 0
            )
            """
        )
        # Best-effort lightweight migrations for older DBs
        cols = {row[1] for row in conn.execute("PRAGMA table_info(rss_data)").fetchall()}
        # Add missing columns with sensible defaults
        if "posted" not in cols:
            conn.execute("ALTER TABLE rss_data ADD COLUMN posted INTEGER DEFAULT 0")
        if "summary" not in cols:
            conn.execute("ALTER TABLE rss_data ADD COLUMN summary TEXT")
        if "published" not in cols:
            conn.execute("ALTER TABLE rss_data ADD COLUMN published TEXT")
        conn.commit()
    except Exception:
        # Avoid masking the original error path; best‑effort initialization only
        pass


def connect() -> sqlite3.Connection:
    global _INIT_DONE
    path = get_db_path()
    # Ensure parent directory exists for new default path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    if not _INIT_DONE:
        _ensure_schema(conn)
        _INIT_DONE = True
    return conn


def query_one(sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
    with connect() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchone()


def query_all(sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: Iterable = ()) -> int:
    with connect() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid if sql.strip().upper().startswith('INSERT') else cur.rowcount
