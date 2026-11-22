"""Read complete role notebooks and publish feedback revisions atomically.

Each role owns one Markdown file. Front matter retains applied feedback IDs for
crash recovery. Only the Markdown body enters a decision. On first use, older
per-entry notes are consolidated in stable ID order without removing originals.
"""
from pathlib import Path
from tempfile import NamedTemporaryFile
import fcntl
import yaml

from assistant.components.data.memory.models import MemoryRole, ROLES, RoleNote


def _document(path):
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}, raw.strip()
    header, separator, body = raw[4:].partition("\n---\n")
    if not separator:
        raise ValueError(f"Incomplete memory front matter: {path.name}")
    return yaml.safe_load(header) or {}, body.strip()


class Memory:
    def __init__(self, directory: Path):
        self.directory = directory

        self._import_legacy_notes()

    def _import_legacy_notes(self):
        legacy = {role: [] for role in ROLES}
        for path in sorted(self.directory.glob("*.md")):
            meta, body = _document(path)
            role = meta.get("role")
            if role in ROLES and meta.get("active", True) and "condition" in meta:
                legacy[role].append(f"{meta['condition']}\n\n{body}")
        for role, sections in legacy.items():
            if sections:
                empty = RoleNote(role=role, content="")
                self.apply(empty, "\n\n".join(sections), "legacy-import")

    def _read(self, role):
        if role not in ROLES:
            raise ValueError(f"Unknown memory role: {role}")
        path = self.directory / f"{role}.md"
        if path.is_file():
            meta, body = _document(path)
            if "condition" not in meta:
                return RoleNote(role=role, content=body), meta.get("applied", [])
        return RoleNote(role=role, content=""), []

    def recall(self, role: MemoryRole) -> RoleNote:
        return self._read(role)[0]

    def apply(self, before: RoleNote, content: str, event_id: str) -> bool:
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current, applied = self._read(before.role)
            if event_id in applied:
                return True
            if before.version != current.version:
                return False
            header = yaml.safe_dump({"applied": [*applied, event_id]}, sort_keys=False)
            stream = NamedTemporaryFile(dir=self.directory, delete=False, mode="w", encoding="utf-8")
            tmp = Path(stream.name)
            try:
                with stream:
                    stream.write(f"---\n{header}---\n{content.strip()}\n")
                tmp.replace(self.directory / f"{before.role}.md")
            finally:
                tmp.unlink(missing_ok=True)
        return True
