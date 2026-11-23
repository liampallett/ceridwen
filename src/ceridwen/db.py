import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "database" / "ceridwen.db"

def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_db(path: Path) -> None:
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


def create_thread(path: Path) -> str:
    conn = _connect(path)
    with conn:
        thread_id = uuid.uuid4().hex
        time = datetime.now(UTC).isoformat()

        conn.execute("""
        INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)
        """,
                           (thread_id, "", time, time))
        return thread_id


def list_threads(path: Path) -> list[dict]:
    conn = _connect(path)
    with conn:
        cur = conn.execute("""
        SELECT * FROM threads ORDER BY updated_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]


def get_messages(path: Path, thread_id: str) -> list[dict]:
    conn = _connect(path)
    with conn:
        messages = []
        cur = conn.execute("""
        SELECT role, content, tool_calls, tool_name FROM messages WHERE thread_id = ? ORDER BY id
        """, (thread_id,))
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
    conn = _connect(path)
    with conn:
        time = datetime.now(UTC).isoformat()
        list_of_tuples = [
            (thread_id,
             message["role"],
             message.get("content"),
             message.get("thinking"),
             json.dumps(message.get("tool_calls")) if "tool_calls" in message else None,
             message.get("tool_name"),
             time,
             ) for message in messages]

        conn.executemany("""
        INSERT INTO messages (thread_id, role, content, thinking, tool_calls, tool_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, list_of_tuples)

        conn.execute("""
        UPDATE threads SET updated_at = ? WHERE id = ?
        """, (time, thread_id))


def delete_thread(path: Path, thread_id: str) -> None:
    conn = _connect(path)
    with conn:
        conn.execute("""
        DELETE FROM threads WHERE id = ?""",
                     (thread_id,))