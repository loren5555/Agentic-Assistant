"""Capability interfaces for curator."""

from typing import Protocol

from assistant.components.coordination.curator.models import CurationDecision
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem


class CuratorProtocol(Protocol):
    """Extract reusable outcomes from a supplied human-accepted result."""

    async def commission(self, source: SourceMaterial, item: WorkbenchItem | None = None) -> CurationDecision:
        """Determine the works, target readers and evidence for source or approved writing."""
        ...

    async def extract(self, item: WorkbenchItem, source: SourceMaterial | None = None) -> CurationDecision:
        """Extract reusable material without publishing it.

        Args:
            item: Human-accepted proposal and result.

        Returns:
            Supported artifacts, or an empty extraction.
        """
        ...
