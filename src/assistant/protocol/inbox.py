"""The provider interface for fetching triggered inbox content."""

from typing import Protocol

from assistant.schemas.inbox import InboxRecord


class InboxSourceProtocol(Protocol):
    """Read Inbox records without modifying source content or processing status."""

    def fetch(self, source_id: str) -> InboxRecord:
        """Read a record identified by its source ID.

        Args:
            source_id: Record ID in the source system; Notion uses a page ID.

        Returns:
            Record content, source identity, and revision information.
            Implementations raise an exception if retrieval fails.
        """
        ...

    def fetch_latest(self) -> InboxRecord | None:
        """Read the most recently updated record in the configured Inbox.

        Returns:
            The most recently updated record, or None if the Inbox is empty.
            Retrieval failures must raise an exception rather than indicate an
            empty Inbox.
        """
        ...
