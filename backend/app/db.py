"""Relational store for candidate profiles and chat messages.

Backend is Postgres (Neon/Supabase) when DATABASE_URL is set, else a local SQLite
file so dev needs zero setup. All SQL lives here; the rest of the app is
storage-agnostic.

Multi-tenancy: every candidate row belongs to a workspace. The shared read-only
"demo" workspace holds the sample corpus; anonymous per-browser workspaces hold
user uploads. Candidates are keyed by (workspace_id, candidate_id).
"""

import json
import sqlite3
from pathlib import Path

from app.config import settings

DB_PATH = Path(__file__).resolve().parent.parent / "cv_checker.db"
IS_PG = bool(settings.database_url)

if IS_PG:
    import psycopg
    from psycopg.rows import dict_row

DEMO_WORKSPACE = "demo"


def _conn():
    if IS_PG:
        return psycopg.connect(settings.database_url, row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _q(sql: str) -> str:
    """Postgres uses %s placeholders; SQLite uses ?."""
    return sql if IS_PG else sql.replace("%s", "?")


def _in_clause(values: list) -> str:
    return ", ".join(["%s"] * len(values))


def init_db() -> None:
    messages_id = (
        "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
        if IS_PG
        else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    timestamp = "TIMESTAMPTZ" if IS_PG else "TEXT"
    with _conn() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS candidates (
                workspace_id     TEXT NOT NULL,
                candidate_id     TEXT NOT NULL,
                name             TEXT NOT NULL,
                current_title    TEXT,
                years_experience REAL,
                location         TEXT,
                summary          TEXT,
                filename         TEXT NOT NULL,
                num_chunks       INTEGER,
                profile_json     TEXT NOT NULL,
                created_at       {timestamp} DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (workspace_id, candidate_id)
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS messages (
                {messages_id},
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at {timestamp} DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")


def upsert_candidate(
    workspace_id: str, candidate_id: str, profile: dict, filename: str, num_chunks: int
) -> None:
    with _conn() as conn:
        conn.execute(
            _q(
                """
                INSERT INTO candidates
                    (workspace_id, candidate_id, name, current_title, years_experience,
                     location, summary, filename, num_chunks, profile_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, candidate_id) DO UPDATE SET
                    name=excluded.name, current_title=excluded.current_title,
                    years_experience=excluded.years_experience, location=excluded.location,
                    summary=excluded.summary, filename=excluded.filename,
                    num_chunks=excluded.num_chunks, profile_json=excluded.profile_json
                """
            ),
            (
                workspace_id,
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


def delete_by_filename(workspace_id: str, filename: str) -> list[str]:
    """Remove candidates previously ingested from this file in this workspace."""
    with _conn() as conn:
        rows = conn.execute(
            _q("SELECT candidate_id FROM candidates WHERE workspace_id = %s AND filename = %s"),
            (workspace_id, filename),
        ).fetchall()
        conn.execute(
            _q("DELETE FROM candidates WHERE workspace_id = %s AND filename = %s"),
            (workspace_id, filename),
        )
    return [row["candidate_id"] for row in rows]


def list_candidates(workspaces: list[str]) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            _q(
                f"""
                SELECT workspace_id, candidate_id, name, current_title, years_experience,
                       location, summary, filename, num_chunks
                FROM candidates WHERE workspace_id IN ({_in_clause(workspaces)})
                ORDER BY name
                """
            ),
            tuple(workspaces),
        ).fetchall()
    return [dict(row) for row in rows]


def get_candidate(candidate_id: str, workspaces: list[str], prefer: str | None = None) -> dict | None:
    """Fetch a candidate visible from `workspaces`; ties broken in favor of `prefer`."""
    prefer = prefer or (workspaces[0] if workspaces else DEMO_WORKSPACE)
    with _conn() as conn:
        row = conn.execute(
            _q(
                f"""
                SELECT * FROM candidates
                WHERE candidate_id = %s AND workspace_id IN ({_in_clause(workspaces)})
                ORDER BY CASE WHEN workspace_id = %s THEN 0 ELSE 1 END
                LIMIT 1
                """
            ),
            (candidate_id, *workspaces, prefer),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["profile"] = json.loads(result.pop("profile_json"))
    result.pop("created_at", None)
    return result


def count_candidates(workspaces: list[str]) -> int:
    with _conn() as conn:
        row = conn.execute(
            _q(f"SELECT COUNT(*) AS n FROM candidates WHERE workspace_id IN ({_in_clause(workspaces)})"),
            tuple(workspaces),
        ).fetchone()
    return row["n"] if IS_PG else row[0]


def add_message(session_id: str, role: str, content: str) -> None:
    with _conn() as conn:
        conn.execute(
            _q("INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)"),
            (session_id, role, content),
        )


def get_history(session_id: str, limit: int = 6) -> list[dict]:
    """Last `limit` messages of a session, oldest first."""
    with _conn() as conn:
        rows = conn.execute(
            _q(
                "SELECT role, content FROM messages WHERE session_id = %s "
                "ORDER BY id DESC LIMIT %s"
            ),
            (session_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
