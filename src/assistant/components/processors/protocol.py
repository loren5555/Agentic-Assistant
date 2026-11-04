"""Source-specific intake and feedback storage operations."""

from typing import Protocol

from assistant.components.inputs.models import SourceMaterial, SourceHistory


class SourceProcessor(Protocol):
    """Read, acknowledge and reopen versions of one source collection."""

    def initialize_schema(self) -> None:
        """Prepare only assistant-owned properties."""
        ...

    def list_pending(self, page_id: str | None = None) -> list[SourceMaterial]:
        """Read eligible inputs.

        Args:
            page_id: Optional explicit source page.

        Returns:
            Source snapshots retaining evidence and human context.
        """
        ...

    def read(self, source: SourceMaterial) -> SourceMaterial:
        """Refresh source scope.

        Args:
            source: Source identity to refresh.

        Returns:
            Current source snapshot.
        """
        ...

    def acknowledge(self, source: SourceMaterial) -> None:
        """Confirm successful proposal intake.

        Args:
            source: Unchanged source version whose proposal was published.
        """
        ...

    def apply_feedback(self, source: SourceMaterial, feedback: SourceHistory) -> SourceMaterial:
        """Append feedback once and reopen the original source.

        Args:
            source: Original work scope.
            feedback: Idempotent feedback round and previous result.

        Returns:
            New or previously updated source version.
        """
        ...
