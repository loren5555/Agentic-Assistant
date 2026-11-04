"""Capability interfaces for captures."""

from typing import Protocol

from assistant.components.captures.models import CaptureBrief, CaptureReceipt, RawCapture


class BriefWriterProtocol(Protocol):
    """Convert available source material into a grounded brief."""

    async def brief(self, capture: RawCapture) -> CaptureBrief:
        """Classify and organize only the supplied material.

        Args:
            capture: Content and provenance available for reading.

        Returns:
            Organized output or a proposal classification.
        """
        ...


class CapturePublisherProtocol(Protocol):
    """Publish organized outputs while preserving human discussion."""

    def initialize_schema(self) -> None:
        """Initialize publication receipt properties in organized destinations."""
        ...

    def publish(self, capture: RawCapture, brief: CaptureBrief) -> CaptureReceipt:
        """Create or update one destination under a stable source key.

        Args:
            capture: Original source and content version.
            brief: Paper or knowledge output; proposals use Workbench separately.

        Returns:
            Receipt after independently reading back the publication.
        """
        ...
