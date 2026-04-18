# db.py
"""SQLite business state. The checkpointer shares the same file but manages
its own tables automatically — no conflict."""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

import tracing

DB_PATH = Path("hitl.sqlite")


def init_db() -> None:
    """Create tables and seed contacts on first run."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drafts (
            draft_id   TEXT PRIMARY KEY,
            recipient  TEXT NOT NULL,
            subject    TEXT NOT NULL,
            body       TEXT NOT NULL,
            created_at REAL NOT NULL,
            status     TEXT NOT NULL DEFAULT 'drafted'
        );
        CREATE TABLE IF NOT EXISTS contacts (
            email     TEXT PRIMARY KEY,
            name      TEXT NOT NULL,
            segments  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sent_log (
            message_id TEXT PRIMARY KEY,
            draft_id   TEXT NOT NULL,
            sent_at    REAL NOT NULL
        );
    """)
    cur = conn.execute("SELECT COUNT(*) FROM contacts")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO contacts (email, name, segments) VALUES (?, ?, ?)",
            [
                ("alice@example.com",  "Alice Chen",    "waitlist,q3"),
                ("bob@example.com",    "Bob Martinez",  "waitlist,q2"),
                ("carol@example.com",  "Carol Singh",   "active,q3"),
                ("dave@example.com",   "Dave Johnson",  "inactive,q3"),
                ("erin@example.com",   "Erin O'Reilly", "inactive,q3"),
                ("frank@example.com",  "Frank Liu",     "inactive,q2"),
                ("legal@example.com",  "Legal Team",    "internal"),
            ],
        )
    conn.commit()
    conn.close()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


def now() -> float:
    return time.time()


def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def dump_rows(table: str, where: str = "", params: tuple = ()) -> list[dict]:
    """Fetch rows as dicts for verbose tracing."""
    conn = connect()
    try:
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
