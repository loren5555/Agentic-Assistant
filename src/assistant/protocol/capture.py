"""Replaceable capture reading, briefing, and publication capabilities."""

from typing import Protocol

from assistant.schemas.capture import CaptureBatch, CaptureBrief, CaptureKind, CaptureReceipt, RawCapture


class CaptureSourceProtocol(Protocol):
    """Read raw paper/article inputs without coupling callers to Notion."""

    def list_captures(self, kind: CaptureKind, limit: int = 20, cursor: str | None = None) -> CaptureBatch:
        """Read one bounded page of inputs.

        Args:
            kind: Collection to scan.
            limit: Maximum number of records in this query.
            cursor: Previous query's continuation token.

        Returns:
            Captures and optional continuation token.
        """
        ...

    def read_capture(self, page_id: str, kind: CaptureKind) -> RawCapture:
        """Read current material before publishing its organized output.

        Args:
            page_id: Original capture page.
            kind: Expected input collection.

        Returns:
            Current capture including its content fingerprint.
        """
        ...

    def mark_handled(self, capture: RawCapture) -> None:
        """Close a verified SimpRead input; leave Notero read-only.

        Args:
            capture: Successfully published or proposed source.
        """
        ...


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

    def publish(self, capture: RawCapture, brief: CaptureBrief) -> CaptureReceipt:
        """Create or update one destination under a stable source key.

        Args:
            capture: Original source and content version.
            brief: Paper or knowledge output; proposals use Workbench separately.

        Returns:
            Receipt after independently reading back the publication.
        """
        ...
