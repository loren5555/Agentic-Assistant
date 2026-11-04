"""Storage boundary for accepted, typed information products."""

from typing import Protocol
from assistant.components.inputs.models import SourceMaterial
from assistant.components.workbench.models import WorkbenchItem
from assistant.components.curator.models import RetainedArtifact
from assistant.components.archive.models import ArchiveReceipt


class PublisherProtocol(Protocol):
    """Publish an accepted artifact without planning or changing review decisions."""

    def initialize_schema(self) -> None:
        """Prepare destination publication keys and reading fields."""
        ...

    def publish(self, source: SourceMaterial, item: WorkbenchItem,
                artifact: RetainedArtifact, key: str) -> ArchiveReceipt:
        """Save an accepted product with its source provenance.

        Args:
            source: Original effective source snapshot.
            item: Accepted Workbench task.
            artifact: Typed output selected for retention.
            key: Stable publication identity across retries.

        Returns:
            Verified output link.
        """
        ...
