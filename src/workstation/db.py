"""4k_workstation_state.db — tüm sistem durumunun tutulduğu SQLite katmanı.

Senkron sqlite3 çağrıları `asyncio.to_thread` ile sarılır; böylece TUI asla bloklanmaz.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS providers (
    name TEXT PRIMARY KEY,
    kind TEXT,
    available INTEGER DEFAULT 0,
    cooldown_until REAL DEFAULT 0,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    provider TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL DEFAULT 0,
    project_id INTEGER
);
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    role TEXT,
    content TEXT,
    provider TEXT
);
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    query TEXT,
    mode TEXT,
    report TEXT
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    name TEXT,
    idea TEXT,
    feasibility_md TEXT,
    status TEXT DEFAULT 'analiz',
    repo_path TEXT,
    budget REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    title TEXT,
    description TEXT,
    branch TEXT,
    worktree_path TEXT,
    status TEXT DEFAULT 'açık'
);
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    project_id INTEGER,
    type TEXT CHECK (type IN ('gelir', 'gider')),
    amount REAL,
    currency TEXT DEFAULT 'TRY',
    category TEXT,
    note TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    project_id INTEGER,
    title TEXT,
    status TEXT DEFAULT 'yapılacak',
    due TEXT
);
CREATE TABLE IF NOT EXISTS nodes (
    name TEXT PRIMARY KEY,
    ip TEXT,
    os TEXT,
    online INTEGER,
    last_seen TEXT
);
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    action TEXT,
    status TEXT,
    detail TEXT
);
"""


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else config.DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # --- senkron çekirdek -------------------------------------------------
    def execute_sync(self, sql: str, params: tuple | dict = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid or cur.rowcount

    def fetchall_sync(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def fetchone_sync(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        rows = self.fetchall_sync(sql, params)
        return rows[0] if rows else None

    # --- asenkron sarmalayıcılar -----------------------------------------
    async def execute(self, sql: str, params: tuple | dict = ()) -> int:
        return await asyncio.to_thread(self.execute_sync, sql, params)

    async def fetchall(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.fetchall_sync, sql, params)

    async def fetchone(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        return await asyncio.to_thread(self.fetchone_sync, sql, params)

    # --- ayarlar ----------------------------------------------------------
    def get_setting_sync(self, key: str, default: str | None = None) -> str | None:
        row = self.fetchone_sync("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting_sync(self, key: str, value: str) -> None:
        self.execute_sync(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        return await asyncio.to_thread(self.get_setting_sync, key, default)

    async def set_setting(self, key: str, value: str) -> None:
        await asyncio.to_thread(self.set_setting_sync, key, value)

    async def log_sync(self, action: str, status: str, detail: str = "") -> None:
        await self.execute(
            "INSERT INTO sync_log(ts, action, status, detail) VALUES(?,?,?,?)",
            (time.time(), action, status, detail),
        )

    # --- yedekleme --------------------------------------------------------
    def snapshot_sync(self, dest: Path) -> Path:
        """Tutarlı bir kopya üretir (WAL dahil)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(dest)
        with self._lock:
            self._conn.backup(target)
        target.close()
        return dest

    def restore_from_sync(self, source: Path) -> None:
        src = sqlite3.connect(source)
        with self._lock:
            src.backup(self._conn)
        src.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
