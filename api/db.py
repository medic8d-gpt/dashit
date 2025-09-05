import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


# Resolve DB path: prefer env `DB_PATH`; else default to `rss_feed_data.db` in project root (dashit/)
def _default_db_path() -> str:
    # Prefer a DB file in the current working directory
    cwd_db = Path.cwd() / 'rss_feed_data.db'
    if cwd_db.exists():
        return str(cwd_db)
    # Fallback: DB at project root (two levels up from this file)
    project_root_db = Path(__file__).resolve().parent.parent / 'rss_feed_data.db'
    return str(project_root_db)


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
