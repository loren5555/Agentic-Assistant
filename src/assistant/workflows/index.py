"""Keep a small application index separate from DBOS's internal tables."""

import sqlite3
from pathlib import Path


class WorkIndex:
    """Map source identities to checkpoint owners without duplicating reports.

    Attributes:
        path: Application-owned SQLite file, not the DBOS system database.
    """

    def __init__(self, path: Path) -> None:
        """Initialize mapping tables used by intake and review polling.

        Args:
            path: Local index database path.
        """
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS work ("
                "source_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
                "workflow_id TEXT NOT NULL, page_id TEXT NOT NULL, status TEXT NOT NULL)"
            )
            connection.execute("CREATE TABLE IF NOT EXISTS cursors (kind TEXT PRIMARY KEY, value TEXT)")

    def get(self, source_key: str) -> dict | None:
        """Find a source's latest checkpoint owner.

        Args:
            source_key: Stable source identity.

        Returns:
            Mapping metadata, or None when not yet processed.
        """
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM work WHERE source_key = ?", (source_key,)).fetchone()
        record = dict(row) if row is not None else None
        return record

    def save(self, source_key: str, fingerprint: str, workflow_id: str, page_id: str, status: str) -> None:
        """Publish the pointer only after its DBOS state event has been saved.

        Args:
            source_key: Original material identity.
            fingerprint: Meaningful source version.
            workflow_id: Workflow owning the current state event.
            page_id: Human-facing Notion page, if any.
            status: Current phase used to bound polling.
        """
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO work VALUES (?, ?, ?, ?, ?) ON CONFLICT(source_key) DO UPDATE SET "
                "fingerprint=excluded.fingerprint, workflow_id=excluded.workflow_id, "
                "page_id=excluded.page_id, status=excluded.status",
                (source_key, fingerprint, workflow_id, page_id, status),
            )

    def active(self) -> list[dict]:
        """List only managed records currently awaiting human review.

        Returns:
            Index rows, not Notion reports or old database entries.
        """
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM work WHERE status IN ('Open', 'Executed')").fetchall()
        records = [dict(row) for row in rows]
        return records

    def cursor(self, kind: str) -> str | None:
        """Read the next bounded capture-query position.

        Args:
            kind: Raw capture collection.

        Returns:
            Continuation token, or None to start a pass.
        """
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT value FROM cursors WHERE kind = ?", (kind,)).fetchone()
        value = row[0] if row else None
        return value

    def save_cursor(self, kind: str, cursor: str | None) -> None:
        """Advance pagination after all records in the current page succeed.

        Args:
            kind: Raw capture collection.
            cursor: Next query token, or None after a complete scan.
        """
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO cursors VALUES (?, ?) ON CONFLICT(kind) DO UPDATE SET value=excluded.value",
                (kind, cursor),
            )
