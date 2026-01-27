from __future__ import annotations

import sqlite3

from agent.config import DB_PATH


def init_db() -> None:
    """Create local DB tables.

    Note: v1 dedup is against the Google Sheet (source of truth).
    This DB exists for local experimentation and visibility.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                context TEXT,
                seen_at TEXT NOT NULL
            );
            """
        )
