"""Verified destinations of retained knowledge and ideas."""

from pydantic import BaseModel


class ArchiveReceipt(BaseModel):
    """Identify a verified retained outcome.

    Attributes:
        key: Stable publication key shared across retries.
        url: Destination page link.
    """

    key: str
    url: str
