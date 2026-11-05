"""Capability interfaces for proposer."""

from typing import Protocol

from assistant.components.data.sources.models import SourceMaterial
from assistant.components.coordination.proposer.models import Proposal


class ProposerProtocol(Protocol):
    """Draft from one effective snapshot containing any prior review feedback."""

    async def draft(self, source: SourceMaterial) -> Proposal:
        """Draft one proposal without changing external storage.

        Args:
            source: Original material to organize into a proposal.

        Returns:
            The grounded proposal with its source fingerprint and version.
        """
        ...
