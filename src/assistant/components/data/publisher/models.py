"""Verified publication receipts.

Input origin:
    Destination writers confirm accepted artifact or brief publication.
Output destination:
    Receipts return to Curator state and workflow checkpoints.
Responsibility:
    Describe confirmed destination writes without choosing what should be retained.
"""

from pydantic import BaseModel


class PublicationReceipt(BaseModel):
    """Identify a verified retained outcome.

    Attributes:
        key: Stable publication key shared across retries.
        url: Destination page link.
    """

    key: str
    url: str


class BriefPublicationReceipt(BaseModel):
    """A verified organized destination write.

    Attributes:
        page_id: Published output identifier.
        url: Human-readable destination link.
        key: Stable source identity used for retry-safe publication.
        fingerprint: Source content version represented by this output.
    """

    page_id: str
    url: str
    key: str
    fingerprint: str
