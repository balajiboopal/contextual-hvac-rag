"""State stores for WhatsApp message processing."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol


class StoreProtocol(Protocol):
    """Protocol shared by all bot state stores."""

    def get_conversation_id(self, wa_id: str) -> str | None:
        """Return the stored conversation id for a WhatsApp user."""

    def set_conversation_id(self, wa_id: str, conversation_id: str) -> None:
        """Persist a conversation id for a WhatsApp user."""

    def get_last_user_message_ts(self, wa_id: str) -> int | None:
        """Return the last inbound user message timestamp."""

    def set_last_user_message_ts(self, wa_id: str, timestamp: int) -> None:
        """Persist the last inbound user message timestamp."""

    def has_processed_message(self, message_id: str) -> bool:
        """Return whether the message id has already been handled."""

    def mark_processed_message(self, message_id: str, processed_at: int) -> None:
        """Persist a message id as processed."""

    def close(self) -> None:
        """Release any store resources."""


class InMemoryStore:
    """Simple process-local store for development."""

    def __init__(self) -> None:
        self._conversation_ids: dict[str, str] = {}
        self._last_user_message_ts: dict[str, int] = {}
        self._processed_message_ids: set[str] = set()

    def get_conversation_id(self, wa_id: str) -> str | None:
        return self._conversation_ids.get(wa_id)

    def set_conversation_id(self, wa_id: str, conversation_id: str) -> None:
        self._conversation_ids[wa_id] = conversation_id

    def get_last_user_message_ts(self, wa_id: str) -> int | None:
        return self._last_user_message_ts.get(wa_id)

    def set_last_user_message_ts(self, wa_id: str, timestamp: int) -> None:
        self._last_user_message_ts[wa_id] = timestamp

    def has_processed_message(self, message_id: str) -> bool:
        return message_id in self._processed_message_ids

    def mark_processed_message(self, message_id: str, processed_at: int) -> None:
        _ = processed_at
        self._processed_message_ids.add(message_id)

    def close(self) -> None:
        return None


class SQLiteStore:
    """SQLite-backed store for local persistence."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                wa_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_activity (
                wa_id TEXT PRIMARY KEY,
                last_user_message_ts INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at INTEGER NOT NULL
            )
            """
        )
        self._connection.commit()

    def get_conversation_id(self, wa_id: str) -> str | None:
        cursor = self._connection.execute(
            "SELECT conversation_id FROM conversations WHERE wa_id = ?",
            (wa_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return str(row["conversation_id"])

    def set_conversation_id(self, wa_id: str, conversation_id: str) -> None:
        self._connection.execute(
            """
            INSERT INTO conversations (wa_id, conversation_id)
            VALUES (?, ?)
            ON CONFLICT(wa_id) DO UPDATE SET conversation_id = excluded.conversation_id
            """,
            (wa_id, conversation_id),
        )
        self._connection.commit()

    def get_last_user_message_ts(self, wa_id: str) -> int | None:
        cursor = self._connection.execute(
            "SELECT last_user_message_ts FROM user_activity WHERE wa_id = ?",
            (wa_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return int(row["last_user_message_ts"])

    def set_last_user_message_ts(self, wa_id: str, timestamp: int) -> None:
        self._connection.execute(
            """
            INSERT INTO user_activity (wa_id, last_user_message_ts)
            VALUES (?, ?)
            ON CONFLICT(wa_id) DO UPDATE SET last_user_message_ts = excluded.last_user_message_ts
            """,
            (wa_id, timestamp),
        )
        self._connection.commit()

    def has_processed_message(self, message_id: str) -> bool:
        cursor = self._connection.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?",
            (message_id,),
        )
        return cursor.fetchone() is not None

    def mark_processed_message(self, message_id: str, processed_at: int) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO processed_messages (message_id, processed_at)
            VALUES (?, ?)
            """,
            (message_id, processed_at),
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

