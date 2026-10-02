"""Content that a source makes available for model context."""

from typing import Protocol


class ContextContent(Protocol):
    """Expose meaningful source content independently of storage metadata."""

    @property
    def context_content(self) -> str:
        """Provide the source's content for model context.

        Returns:
            Text describing the meaningful content of the source.
        """
        ...
