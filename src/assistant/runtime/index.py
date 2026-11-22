"""Keep a small application index separate from DBOS's internal tables."""

from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import date, timedelta


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
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS work ("
                "source_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
                "workflow_id TEXT NOT NULL, page_id TEXT NOT NULL, status TEXT NOT NULL)"
            )
            connection.execute("CREATE TABLE IF NOT EXISTS source_acknowledgements ("
                               "submitted TEXT PRIMARY KEY, acknowledged TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS recommendation_coverage ("
                               "identity TEXT PRIMARY KEY, breadth TEXT, age TEXT, day TEXT)")

    def coverage_counts(self, day: str, days: int) -> dict[str, int]:
        """Read rolling publication coverage using age at publication time."""
        start = (date.fromisoformat(day) - timedelta(days=days-1)).isoformat()
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT breadth || ':' || age, COUNT(*) FROM recommendation_coverage "
                "WHERE day BETWEEN ? AND ? AND age != 'unknown' GROUP BY breadth, age", (start, day),
            ).fetchall()
        return dict(rows)

    def record_coverage(self, identity: str, breadth: str, published: str, day: str) -> None:
        """Count confirmed publication once; keep its original age bucket stable."""
        from assistant.components.recommendations.collector.policy import age_bucket
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT OR IGNORE INTO recommendation_coverage VALUES (?, ?, ?, ?)",
                               (identity, breadth, age_bucket(published, day), day))

    def recommendation_counts(self) -> dict[str, int]:
        """Read actual editorial coverage used by long-term exploration targets."""
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS editions (identity TEXT PRIMARY KEY, breadth TEXT, day TEXT)")
            rows = connection.execute("SELECT breadth, COUNT(*) FROM editions GROUP BY breadth").fetchall()
        return dict(rows)

    def record_recommendation(self, identity: str, breadth: str, day: str) -> None:
        """Count each confirmed source once, including publication retries."""
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS editions (identity TEXT PRIMARY KEY, breadth TEXT, day TEXT)")
            connection.execute("INSERT OR IGNORE INTO editions VALUES (?, ?, ?)", (identity, breadth, day))

    def get(self, source_key: str) -> dict | None:
        """Find a source's latest checkpoint owner.

        Args:
            source_key: Stable source identity.

        Returns:
            Mapping metadata, or None when not yet processed.
        """
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT w.*, a.acknowledged AS acknowledged_snapshot FROM work w "
                "LEFT JOIN source_acknowledgements a ON a.submitted=w.fingerprint WHERE w.source_key=?",
                (source_key,),
            ).fetchone()
        record = dict(row) if row is not None else None
        return record

    def is_acknowledged(self, snapshot: str) -> bool:
        """Recognize handled inputs including archive-only and no-action outcomes."""
        with closing(sqlite3.connect(self.path)) as connection:
            return connection.execute("SELECT 1 FROM source_acknowledgements WHERE acknowledged=? LIMIT 1",
                                      (snapshot,)).fetchone() is not None

    def record_acknowledgement(self, submitted: str, acknowledged: str) -> None:
        """Recognize the timestamp produced by our own successful source update."""
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT OR REPLACE INTO source_acknowledgements VALUES (?, ?)",
                               (submitted, acknowledged))

    def save(self, source_key: str, fingerprint: str, workflow_id: str, page_id: str, status: str) -> None:
        """Publish the pointer only after its DBOS state event has been saved.

        Args:
            source_key: Original material identity.
            fingerprint: Meaningful source version.
            workflow_id: Workflow owning the current state event.
            page_id: Human-facing Notion page, if any.
            status: Current phase used to bound polling.
        """
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO work VALUES (?, ?, ?, ?, ?) ON CONFLICT(source_key) DO UPDATE SET "
                "fingerprint=excluded.fingerprint, workflow_id=excluded.workflow_id, "
                "page_id=excluded.page_id, status=excluded.status",
                (source_key, fingerprint, workflow_id, page_id, status),
            )

    def list_active(self) -> list[dict]:
        """List only managed records currently awaiting human review.

        Returns:
            Index rows, not Notion reports or old database entries.
        """
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM work WHERE status IN ('Open', 'Needs Input', 'Executed')").fetchall()
        records = [dict(row) for row in rows]
        return records
