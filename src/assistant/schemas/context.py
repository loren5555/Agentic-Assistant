"""Working information retained for future context retrieval."""

from pydantic import BaseModel

from .input import SourceReference


class ContextNote(BaseModel):
    """Preserve working information for later retrieval, not publication."""

    title: str
    content: str
    sources: list[SourceReference]
    simulated: bool = True
