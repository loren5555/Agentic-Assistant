"""Read submitted material and acknowledge verified processing."""

from typing import Protocol

class ContextContent(Protocol):
    """Expose meaningful source content independently of storage metadata."""

    @property
    def context_content(self) -> str:
        """Provide meaningful material for model context.

        Returns:
            Human-readable source content without storage metadata.
        """
        ...
