"""Knowledge prepared for publication and the resulting draft receipt."""

from pydantic import BaseModel

from .input import SourceReference


class KnowledgeNote(BaseModel):
    """Capture knowledge prepared for review and publication as a draft."""

    title: str
    content: str
    sources: list[SourceReference]
    simulated: bool = True


class DraftReceipt(BaseModel):
    id: str
    note: KnowledgeNote
