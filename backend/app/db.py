"""SQLite store for extracted candidate profiles (one row per candidate).

The vector store holds chunk text + minimal identity metadata; the full
profile JSON lives here, joined on candidate_id.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "cv_checker.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id     TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                current_title    TEXT,
                years_experience REAL,
                location         TEXT,
                summary          TEXT,
                filename         TEXT NOT NULL,
                num_chunks       INTEGER,
                profile_json     TEXT NOT NULL,
                created_at       TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")


def upsert_candidate(candidate_id: str, profile: dict, filename: str, num_chunks: int) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO candidates
                (candidate_id, name, current_title, years_experience, location,
                 summary, filename, num_chunks, profile_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                name=excluded.name, current_title=excluded.current_title,
                years_experience=excluded.years_experience, location=excluded.location,
                summary=excluded.summary, filename=excluded.filename,
                num_chunks=excluded.num_chunks, profile_json=excluded.profile_json
            """,
            (
                candidate_id,
                profile.get("name", ""),
                profile.get("current_title", ""),
                profile.get("years_experience", 0),
                profile.get("location", ""),
                profile.get("summary", ""),
                filename,
                num_chunks,
                json.dumps(profile, ensure_ascii=False),
            ),
        )


def delete_by_filename(filename: str) -> list[str]:
    """Remove any candidates previously ingested from this file; return their ids."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT candidate_id FROM candidates WHERE filename = ?", (filename,)
        ).fetchall()
        conn.execute("DELETE FROM candidates WHERE filename = ?", (filename,))
    return [row["candidate_id"] for row in rows]


def list_candidates() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT candidate_id, name, current_title, years_experience,
                   location, summary, filename, num_chunks, created_at
            FROM candidates ORDER BY name
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_candidate(candidate_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["profile"] = json.loads(result.pop("profile_json"))
    return result


def count_candidates() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]


def add_message(session_id: str, role: str, content: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def get_history(session_id: str, limit: int = 6) -> list[dict]:
    """Last `limit` messages of a session, oldest first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]
