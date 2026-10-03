"""Interfaces for accepted-result curation and long-term outcome storage."""

from typing import Protocol

from assistant.schemas.curation import ArchiveReceipt, CurationCycle, RetainedArtifact
from assistant.schemas.proposal import WorkbenchItem


class CuratorProtocol(Protocol):
    """Own extraction and finalization of human-accepted results."""

    async def run_cycle(self) -> CurationCycle:
        """Retain useful outcomes and finalize accepted tasks.

        Returns:
            Finished and archived links, and failures awaiting recovery.
        """
        ...


class ArchiveStoreProtocol(Protocol):
    """Save useful outcomes independently of workflow implementation."""

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
