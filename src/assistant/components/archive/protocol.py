"""Capability interfaces for archive."""

from typing import Protocol

from assistant.components.archive.models import ArchiveReceipt
from assistant.components.curator.models import RetainedArtifact
from assistant.components.workbench.models import WorkbenchItem


class ArchiveStoreProtocol(Protocol):
    """Save useful outcomes independently of workflow implementation."""

    def initialize_schema(self) -> None:
        """Explicitly prepare stable publication identities in archive storage."""
        ...

    def publish(
        self, item: WorkbenchItem, artifact: RetainedArtifact, key: str,
    ) -> ArchiveReceipt:
        """Save or recover a retained outcome under a stable key.

        Args:
            item: Accepted task supplying provenance.
            artifact: Grounded material to retain.
            key: Identifier shared across retries of the same extraction.

        Returns:
            Receipt verified against the destination page.
        """
        ...
