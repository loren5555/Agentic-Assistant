"""Capability interfaces for curator."""

from typing import Protocol

from assistant.components.curator.models import CurationDecision
from assistant.components.workbench.models import WorkbenchItem


class CuratorProtocol(Protocol):
    """Extract reusable outcomes from a supplied human-accepted result."""

    async def extract(self, item: WorkbenchItem) -> CurationDecision:
        """Extract reusable material without publishing it.

        Args:
            item: Human-accepted proposal and result.

        Returns:
            Supported artifacts, or an empty extraction.
        """
        ...
