"""Capability interfaces for proposer."""

from typing import Protocol

from assistant.components.inputs.models import SourceMaterial
from assistant.components.proposer.models import Proposal
from assistant.components.workbench.models import WorkbenchItem


class ProposerProtocol(Protocol):
    """Draft a proposal using supplied material and optional review feedback."""

    async def draft(self, source: SourceMaterial, previous: WorkbenchItem | None = None) -> Proposal:
        """Draft one proposal without changing external storage.

        Args:
            source: Original material to organize into a proposal.
            previous: Current report and feedback when revising.

        Returns:
            The grounded proposal with its source fingerprint and version.
        """
        ...
