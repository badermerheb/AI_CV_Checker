"""One-off migration to Postgres + workspaces.

- Creates the new schema on DATABASE_URL (Neon)
- Copies candidate profiles from the legacy local SQLite file:
  sample CVs -> the shared 'demo' workspace, the owner's personal CV -> a
  private workspace that public visitors never see
- Tags every existing Qdrant point (local AND cloud) with its workspace_id

Run from backend/:  .venv/Scripts/python scripts/migrate_workspaces.py
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import dotenv_values
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

from app import db

LEGACY_SQLITE = Path(__file__).resolve().parent.parent / "cv_checker.db"
PRIVATE_WORKSPACE = "owner-private"
PRIVATE_FILENAMES = {"badermerheb_cv.pdf"}


def migrate_profiles() -> dict[str, str]:
    """Copy legacy SQLite rows into Postgres. Returns candidate_id -> workspace."""
    assignments: dict[str, str] = {}
    if not LEGACY_SQLITE.exists():
        print("no legacy sqlite file; skipping profile copy")
        return assignments
    conn = sqlite3.connect(LEGACY_SQLITE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM candidates").fetchall()
    for row in rows:
        workspace = (
            PRIVATE_WORKSPACE if row["filename"].lower() in PRIVATE_FILENAMES else "demo"
        )
        db.upsert_candidate(
            workspace,
            row["candidate_id"],
            json.loads(row["profile_json"]),
            row["filename"],
            row["num_chunks"],
        )
        assignments[row["candidate_id"]] = workspace
    conn.close()
    print(f"copied {len(rows)} profiles to Postgres "
          f"({sum(1 for w in assignments.values() if w == 'demo')} demo, "
          f"{sum(1 for w in assignments.values() if w != 'demo')} private)")
    return assignments


def tag_qdrant(client: QdrantClient, label: str, assignments: dict[str, str]) -> None:
    if not client.collection_exists("cv_chunks"):
        print(f"{label}: no cv_chunks collection")
        return
    from app.vectorstore import ensure_payload_indexes

    ensure_payload_indexes(client)
    # Default every untagged point to 'demo'...
    client.set_payload(
        collection_name="cv_chunks",
        payload={"workspace_id": "demo"},
        points=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.IsEmptyCondition(is_empty=qmodels.PayloadField(key="workspace_id"))]
            )
        ),
    )
    # ...then move private candidates out of the public corpus.
    for candidate_id, workspace in assignments.items():
        if workspace == "demo":
            continue
        client.set_payload(
            collection_name="cv_chunks",
            payload={"workspace_id": workspace},
            points=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="candidate_id", match=qmodels.MatchValue(value=candidate_id)
                        )
                    ]
                )
            ),
        )
    demo = client.count(
        "cv_chunks",
        count_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="workspace_id", match=qmodels.MatchValue(value="demo"))]
        ),
    ).count
    print(f"{label}: {demo} points in demo workspace, {client.count('cv_chunks').count} total")


def main() -> None:
    db.init_db()
    print("schema ready on", "Postgres" if db.IS_PG else "SQLite")
    assignments = migrate_profiles()

    env = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
    tag_qdrant(QdrantClient(url="http://localhost:6333"), "local qdrant", assignments)
    if env.get("QDRANT_CLOUD_URL"):
        tag_qdrant(
            QdrantClient(url=env["QDRANT_CLOUD_URL"], api_key=env.get("QDRANT_API_KEY")),
            "cloud qdrant",
            assignments,
        )


if __name__ == "__main__":
    main()
