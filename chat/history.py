"""对话历史存储。

借鉴了开源桌宠 yoji（MIT）的做法：消息和摘要分两张表。
它那边用 prev_id/next_id 链表存，这里换成普通自增表——
桌宠规模用不上链表，多一层指针只会让查询变绕。
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from app.paths import db_path


class History:
    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path else db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    upto INTEGER NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    # ---- 消息 ----
    def add(self, role: str, content: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, time.time()),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def max_id(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT MAX(id) AS m FROM messages").fetchone()
            return int(row["m"] or 0)

    def recent_since(self, upto: int, limit: int) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE id > ? ORDER BY id DESC LIMIT ?",
                (upto, limit),
            ).fetchall()
        return list(reversed(rows))

    def count_since(self, upto: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE id > ?", (upto,)
            ).fetchone()
            return int(row["c"] or 0)

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.execute("DELETE FROM summaries")
            self._conn.commit()

    # ---- 摘要 ----
    def latest_summary(self) -> tuple[str, int]:
        with self._lock:
            row = self._conn.execute(
                "SELECT content, upto FROM summaries ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return "", 0
        return row["content"], int(row["upto"])

    def replace_summary(self, content: str, upto: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM summaries")
            self._conn.execute(
                "INSERT INTO summaries (content, upto, created_at) VALUES (?, ?, ?)",
                (content, upto, time.time()),
            )
            self._conn.commit()
