"""Storage boundary for accepted, typed information products."""

from typing import Protocol
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.components.data.publisher.models import PublicationReceipt
from assistant.components.execution.briefer.models import ReadingBrief, ReadingMaterial
from assistant.components.data.publisher.models import BriefPublicationReceipt


class PublisherProtocol(Protocol):
    """Publish an accepted artifact without planning or changing review decisions."""

    def initialize_schema(self) -> None:
        """Prepare destination publication keys and reading fields."""
        ...

    def publish(self, source: SourceMaterial, item: WorkbenchItem,
                artifact: RetainedArtifact, key: str) -> PublicationReceipt:
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


class ArtifactPublisherProtocol(Protocol):
    """Save useful outcomes independently of workflow implementation."""

    def initialize_schema(self) -> None:
        """Explicitly prepare stable publication identities in archive storage."""
        ...

    def publish(
        self, item: WorkbenchItem, artifact: RetainedArtifact, key: str,
    ) -> PublicationReceipt:
        """Save or recover a retained outcome under a stable key.

        Args:
            item: Accepted task supplying provenance.
            artifact: Grounded material to retain.
            key: Identifier shared across retries of the same extraction.

        Returns:
            Receipt verified against the destination page.
        """
        ...


class BriefPublisherProtocol(Protocol):
    """Publish organized outputs while preserving human discussion."""

    def initialize_schema(self) -> None:
        """Initialize publication receipt properties in organized destinations."""
        ...

    def publish(self, capture: ReadingMaterial, brief: ReadingBrief) -> BriefPublicationReceipt:
        """Create or update one destination under a stable source key.

        Args:
            capture: Original source and content version.
            brief: Paper or knowledge output; proposals use Workbench separately.

        Returns:
            Receipt after independently reading back the publication.
        """
        ...
