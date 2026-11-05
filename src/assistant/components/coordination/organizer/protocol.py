"""Interpret inputs without owning their lifecycle."""

from typing import Protocol
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.coordination.organizer.models import OrganizedInformation


class OrganizerProtocol(Protocol):
    """Organize one effective input snapshot."""

    async def organize(self, source: SourceMaterial) -> OrganizedInformation:
        """Identify grounded knowledge and action signals.

        Args:
            source: Full effective material and human intent.

        Returns:
            Interpretation for proposal drafting, not an execution result.
        """
        ...
