"""Read submitted material and acknowledge verified processing."""

from typing import Protocol

from assistant.components.inputs.models import SourceMaterial


class ContextContent(Protocol):
    """Expose meaningful source content independently of storage metadata."""

    @property
    def context_content(self) -> str:
        """Provide meaningful material for model context.

        Returns:
            Human-readable source content without storage metadata.
        """
        ...


class InputSourceProtocol(Protocol):
    """Own source reads and completion acknowledgements."""

    def list_inputs(self) -> list[SourceMaterial]:
        """Read unarchived Inbox and elevated TODO material.

        Returns:
            Materials awaiting intake.
        """
        ...

    def read_source(self, source_url: str) -> SourceMaterial:
        """Read original material regardless of its intake status.

        Args:
            source_url: Original input link.

        Returns:
            Current source material.
        """
        ...

    def close_source(self, source: SourceMaterial) -> None:
        """Mark successfully submitted input as handled.

        Args:
            source: Inbox to archive or TODO to mark handled.
        """
        ...
