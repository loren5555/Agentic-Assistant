"""The independent capability responsible for managing proposals."""

from typing import Protocol

from assistant.schemas.proposal import ProposalCycle, Proposal, SourceMaterial, WorkbenchItem


class ProposerProtocol(Protocol):
    """Manage intake, resubmissions, and human review in one cycle."""

    async def draft(self, source: SourceMaterial, previous: WorkbenchItem | None = None) -> Proposal:
        """Draft one proposal without changing external storage.

        Args:
            source: Original material to organize into a proposal.
            previous: Current report and feedback when revising.

        Returns:
            The grounded proposal with its source fingerprint and version.
        """
        ...

    async def run_cycle(self) -> ProposalCycle:
        """Process source material and review decisions.

        Returns:
            Changed proposal links and approved tasks awaiting execution.
        """
        ...
