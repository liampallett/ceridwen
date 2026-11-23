"""SQLite storage for threads (conversations) and their messages.

Every function takes the database path, so tests can use a temporary file.
Messages are stored one row per turn, in the same shape the agent uses, so a
loaded thread can be passed straight back to the model.
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path


def _connect(path: Path) -> sqlite3.Connection:
    """Open a connection with dict-like rows and foreign keys enforced.

    Creates the database's parent folder if it doesn't exist yet. SQLite only
    enforces foreign keys (and so cascading deletes) when asked, per
    connection, which is why every connection goes through here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_db(path: Path) -> None:
    """Create the ``threads`` and ``messages`` tables if they don't exist.

    Safe to call on every startup.
    """
    conn = _connect(path)
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT,
            thinking TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            created_at TEXT
        );
        """)


def thread_exists(path: Path, thread_id: str) -> bool:
    """Return whether a thread with this ID exists."""
    conn = _connect(path)
    with conn:
        cur = conn.execute(
            """
        SELECT 1 FROM threads WHERE id = ?
        """,
            (thread_id,),
        )
        return cur.fetchone() is not None


def create_thread(path: Path) -> str:
    """Create an empty, untitled thread and return its ID (a hex UUID)."""
    conn = _connect(path)
    with conn:
        thread_id = uuid.uuid4().hex
        time = datetime.now(UTC).isoformat()

        conn.execute(
            """
        INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)
        """,
            (thread_id, "", time, time),
        )
        return thread_id


def list_threads(path: Path) -> list[dict]:
    """Return every thread, most recently updated first.

    Each thread is a dict with ``id``, ``title``, ``created_at`` and
    ``updated_at``.
    """
    conn = _connect(path)
    with conn:
        cur = conn.execute("""
        SELECT * FROM threads ORDER BY updated_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]


def get_messages(path: Path, thread_id: str) -> list[dict]:
    """Return a thread's messages, oldest first, in Ollama's message format.

    Every message has ``role`` and ``content`` (never ``None``). Assistant
    messages that called tools also have ``tool_calls``, and tool results
    have ``tool_name``; the keys are left out entirely when they don't apply.
    Thinking is stored but not returned, since it isn't sent back to the model.

    Returns an empty list for a thread with no messages or an unknown ID.
    """
    conn = _connect(path)
    with conn:
        messages = []
        cur = conn.execute(
            """
        SELECT role, content, tool_calls, tool_name FROM messages WHERE thread_id = ? ORDER BY id
        """,
            (thread_id,),
        )
        rows = cur.fetchall()
        for row in rows:
            message = {"role": row["role"], "content": row["content"] or ""}
            if row["tool_calls"]:
                message["tool_calls"] = json.loads(row["tool_calls"])
            if row["tool_name"]:
                message["tool_name"] = row["tool_name"]
            messages.append(message)
        return messages


def add_messages(path: Path, thread_id: str, messages: list[dict]) -> None:
    """Append messages to a thread and mark it as just updated.

    All or nothing: if any message can't be saved, none of them are.

    Raises:
        KeyError: A message has no ``role``.
        sqlite3.IntegrityError: The thread doesn't exist.
    """
    conn = _connect(path)
    with conn:
        time = datetime.now(UTC).isoformat()
        list_of_tuples = [
            (
                thread_id,
                message["role"],
                message.get("content"),
                message.get("thinking"),
                json.dumps(message.get("tool_calls"))
                if "tool_calls" in message
                else None,
                message.get("tool_name"),
                time,
            )
            for message in messages
        ]

        conn.executemany(
            """
        INSERT INTO messages (thread_id, role, content, thinking, tool_calls, tool_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            list_of_tuples,
        )

        conn.execute(
            """
        UPDATE threads SET updated_at = ? WHERE id = ?
        """,
            (time, thread_id),
        )


def delete_thread(path: Path, thread_id: str) -> None:
    """Delete a thread; its messages are removed with it by the cascade."""
    conn = _connect(path)
    with conn:
        conn.execute(
            """
        DELETE FROM threads WHERE id = ?""",
            (thread_id,),
        )
