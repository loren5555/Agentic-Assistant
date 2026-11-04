"""Visible discovery records shared by search, personalization and selection."""

from pydantic import BaseModel
from assistant.components.recommendations.models import PaperCandidate


class DiscoveryEntry(BaseModel):
    """Keep source metadata and human feedback independently of feed selection.

    Attributes:
        candidate: Public source identity and lightweight discovery description.
        page_id: Editable Notion pool record.
        url: Pool page URL, distinct from the original source link.
        feedback: Interested, Not Interested or empty; silence is neutral.
        selected: Whether the item has already appeared in Research Feed.
    """

    candidate: PaperCandidate
    page_id: str
    url: str = ""
    feedback: str = ""
    selected: bool = False
