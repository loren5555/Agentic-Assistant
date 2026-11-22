"""Whole role notes and the evidence used to revise them."""
from hashlib import sha256
from typing import Annotated, Literal
from pydantic import BaseModel, Field

MemoryRole = Literal["organizer", "proposer"]
ROLES: tuple[MemoryRole, ...] = ("organizer", "proposer")
NoteText = Annotated[str, Field(max_length=4000)]


class RoleNote(BaseModel):
    role: MemoryRole
    content: str

    @property
    def version(self) -> str:
        return sha256(self.content.encode()).hexdigest()


class ReviewFeedback(BaseModel):
    page_id: str
    page: str
    version: int
    stage: Literal["proposal", "result"]
    decision: str
    comment: str
    title: str
    source_kind: str
    context: str

    @property
    def event_id(self) -> str:
        identity = self.model_dump_json(include={"page_id", "version", "stage", "decision", "comment"})
        return sha256(identity.encode()).hexdigest()


class MemoryRevision(BaseModel):
    """Complete replacement notes. Null preserves a note. Empty text clears it."""
    reason: str
    organizer: NoteText | None
    proposer: NoteText | None
