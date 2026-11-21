"""Keep independently reviewable BrainStorm candidates beside the local workflow index.

Each candidate starts as a snapshot of cited report items. Workbench feedback reopens
only that candidate for ordinary proposal intake. The seed paper or active Idea
remains the human-facing provenance link. Completed seed revisions guide the next
automatic search while DBOS keeps the full exploration and assessment checkpoints.
"""

from contextlib import closing
from pathlib import Path
import sqlite3

from assistant.components.data.sources.models import SourceHistory, SourceMaterial
from logger import get_logger, trace_call


logger = get_logger("plugins.data.sources.brainstorm")


class BrainstormProcessor:
    """Store candidate versions and completed exploration receipts."""

    def __init__(self, path: Path, limit: int = 20) -> None:
        self.path = path
        self.limit = limit
        self.initialize_schema()

    def initialize_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS candidates (id TEXT PRIMARY KEY, source TEXT NOT NULL, pending INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS explored (mode TEXT, seed TEXT, revision TEXT NOT NULL, PRIMARY KEY(mode,seed))")

    def handled_versions(self, mode: str, page_ids: list[str]) -> dict[str, str]:
        """Check receipts only for the current library window."""
        if not page_ids:
            return {}
        placeholders = ",".join("?" for _ in page_ids)
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(f"SELECT seed,revision FROM explored WHERE mode=? AND seed IN ({placeholders})",
                              [mode, *page_ids])
            return dict(rows)

    def finish(self, mode: str, seed_id: str, revision: str) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO explored VALUES (?,?,?) ON CONFLICT(mode,seed) DO UPDATE SET "
                       "revision=MAX(revision,excluded.revision)", (mode, seed_id, revision))

    def stage(self, source: SourceMaterial) -> None:
        """Record one original scope. Initial submission belongs to the parent report."""
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR IGNORE INTO candidates VALUES (?,?,0)", (source.page_id, source.model_dump_json()))

    def read(self, source: SourceMaterial) -> SourceMaterial:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT source FROM candidates WHERE id=?", (source.page_id,)).fetchone()
        if row is None:
            raise KeyError(f"Missing BrainStorm proposal source: {source.title}")
        return SourceMaterial.model_validate_json(row[0])

    @trace_call("component", "processor.list_pending")
    def list_pending(self, page_id: str | None = None) -> list[SourceMaterial]:
        logger.debug("Reading BrainStorm candidates reopened by human feedback.")
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute("SELECT source FROM candidates WHERE pending=1 AND (? IS NULL OR id=?) "
                              "ORDER BY rowid LIMIT ?", (page_id, page_id, self.limit)).fetchall()
        logger.debug("Reopened BrainStorm candidates read: count=%d.", len(rows))
        return [SourceMaterial.model_validate_json(row[0]) for row in rows]

    def acknowledge(self, source: SourceMaterial) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT source FROM candidates WHERE id=?", (source.page_id,)).fetchone()
            if row and SourceMaterial.model_validate_json(row[0]).fingerprint == source.fingerprint:
                db.execute("UPDATE candidates SET pending=0 WHERE id=?", (source.page_id,))

    def apply_feedback(self, source: SourceMaterial, feedback: SourceHistory) -> SourceMaterial:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT source FROM candidates WHERE id=?", (source.page_id,)).fetchone()
            if row is None:
                raise KeyError(f"Missing BrainStorm proposal source: {source.title}")
            current = SourceMaterial.model_validate_json(row[0])
            if any(entry.key == feedback.key for entry in current.history):
                return current
            if current.fingerprint != source.fingerprint:
                raise ValueError(f"BrainStorm proposal already changed: {source.title}")
            current.history.append(feedback)
            current.supplement = "\n\n".join(filter(None, [current.supplement, feedback.feedback]))
            current.version += 1
            db.execute("UPDATE candidates SET source=?,pending=1 WHERE id=?", (current.model_dump_json(), current.page_id))
            return current
